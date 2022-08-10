from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .apps import up_notations


@csrf_exempt
def core(request):
    # If there were changes in the Google Sheets.
    if 'X-Goog-Resource-State' in request.headers and request.headers['X-Goog-Resource-State'] == 'update' \
            and 'X-Goog-Changed' in request.headers and 'content' in request.headers['X-Goog-Changed']:
        up_notations()

    return HttpResponse(f"")
