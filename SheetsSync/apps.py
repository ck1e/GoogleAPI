import os
import sys
import time
import uuid

from pathlib import Path, PurePath
from datetime import datetime

from django.conf import settings
from django.apps import AppConfig

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apscheduler.schedulers.background import BackgroundScheduler

# Webhook address
WEBHOOK_ADDRESS = ''

# Path to token file.
TOKEN_FILE = Path(PurePath(settings.BASE_DIR, 'server/creds/token.json'))

# Path to OAuth file.
CREDENTIALS_FILE = Path(PurePath(settings.BASE_DIR, 'server/creds/client-secret.json'))

# OAuth credentials
CREDENTIALS = None

# List use Google services.
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive']

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = ''
RANGE_NAME = ''


# Creates a default Background Scheduler
scheduler = BackgroundScheduler()


class SheetsSyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'SheetsSync'

    def ready(self):
        if 'runserver' in sys.argv:
            if os.environ.get('RUN_MAIN', None) != 'true':
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = \
                    str(Path(PurePath(settings.BASE_DIR, 'server/creds/service-account.json')))

                # Create an access token Google OAuth
                get_credentials()

                # Calling a recursive reconnect function
                re_connect_channel_notifications()

                scheduler.start()
        return None


def connect_channel_notifications(file_id: str = SPREADSHEET_ID,
                                  address: str = WEBHOOK_ADDRESS,
                                  expiration: int = 32503680000) -> dict:
    """Connect the target file change notification channel.

    Parameters
    ----------
    address : basestring
        Webhook address
    expiration : int.
        Time at which the webhook will die
    file_id : basestring.
        Tracking file id

    Returns
    ----------
    Standard python dictionary
    """

    try:
        from .models import ChannelNotification

        service = build('drive', 'v3', credentials=CREDENTIALS)

        # Connect to file change notifications.
        chanel = service.files().watch(fileId=file_id, body={
            'kind': 'api#channel',
            'id': str(uuid.uuid4()),
            'type': 'webhook',
            'address': address,
            'expiration': expiration * 1000,
        }).execute()

        # Adding a channel entry to the database.
        ChannelNotification(
            resourceId=chanel['resourceId'],
            channelId=chanel['id'],
            expiration=chanel['expiration']
        ).save()

        return chanel
    except HttpError as err:
        print(err)


def disconnect_channel_notifications(channels=False) -> None:
    """Disconnect the target file change notification channel.

    Parameters
    ----------
    credentials : Google OAuth credentials object.
    channels : django.db.models.query.QuerySet or list.
        Notification channel list
    """

    try:
        from .models import ChannelNotification

        service = build('drive', 'v3', credentials=CREDENTIALS)

        # Get and delete notification channels and unsubscribing from notifications
        if not channels:
            channels = ChannelNotification.objects.all()

        for channel in channels:
            service.channels().stop(body={
                "id": channel.channelId,
                "resourceId": channel.resourceId
            }).execute()
            channel.delete()
    except HttpError as err:
        print(err)


def re_connect_channel_notifications() -> None:
    from .models import ChannelNotification

    # Get all channel notification
    channels = list(ChannelNotification.objects.all())
    if len(channels) == 0:
        # Subscribing new channel notification
        channel_expiration = int(connect_channel_notifications()['expiration']) / 1000
    elif len(channels) > 1:
        channel_expiration = channels[-1].expiration
        del channels[-1]

        # Unsubscribing from all possible notification channels
        disconnect_channel_notifications(channels)
    elif channels[0].expiration < time.time():
        disconnect_channel_notifications(channels)
        channel_expiration = int(connect_channel_notifications()['expiration']) / 1000
    else:
        channel_expiration = channels[0].expiration

    # Adding a scheduled job to unsubscribing notification channels
    scheduler.add_job(re_connect_channel_notifications,
                      'date',
                      run_date=datetime.utcfromtimestamp(channel_expiration),
                      timezone='UTC',
                      replace_existing=True)

    scheduler.print_jobs()


def up_notations(spreadsheet_id: str = SPREADSHEET_ID, range_name: str = RANGE_NAME) -> None:
    """Updating data in a database based on a file (Google Sheets).

    Parameters
    ----------
    spreadsheet_id : basestring.
        ID spreadsheet
    range_name : basestring.
        Range name
    """

    try:
        from .models import Order

        service = build('sheets', 'v4', credentials=CREDENTIALS)

        # Get data from the file and delete the first line (titles).
        values = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            majorDimension='ROWS'
        ).execute()
        del values['values'][0]

        # Adding or updating data in the database.
        with Order.objects.bulk_update_or_create_context(['number', 'time', 'cost'],
                                                         match_field='id',
                                                         batch_size=10) as bulkit:
            for order in values['values']:
                bulkit.queue(
                    Order(id=order[0],
                          number=order[1],
                          time=datetime.strptime(order[3], "%d.%m.%Y").strftime("%Y-%m-%d"),
                          cost=order[2],
                          )
                )

    except HttpError as err:
        print(err)


def get_credentials(token_file: Path = TOKEN_FILE,
                    credentials_file: Path = CREDENTIALS_FILE,
                    scopes: list[str] = SCOPES) -> Credentials:
    """Creates and obtains an access token for Google API.

    Parameters
    ----------
    token_file : Path.
        Path to token file
    credentials_file : Path.
        Path to credentials file
    scopes : list.
        List of used Google services
    """

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.

    global CREDENTIALS
    if token_file.is_file():
        CREDENTIALS = Credentials.from_authorized_user_file(token_file, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not CREDENTIALS or not CREDENTIALS.valid:
        if CREDENTIALS and CREDENTIALS.expired and CREDENTIALS.refresh_token:
            CREDENTIALS.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
            CREDENTIALS = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(CREDENTIALS.to_json())
