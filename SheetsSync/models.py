from datetime import datetime
from django.db import models
from bulk_update_or_create import BulkUpdateOrCreateQuerySet

import xml.etree.ElementTree as ET
import requests


class Order(models.Model):
    objects = BulkUpdateOrCreateQuerySet.as_manager()
    number = models.IntegerField(verbose_name="Order number", null=True)
    time = models.DateField(verbose_name="Order delivery time", null=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Order cost, $", null=True)
    cost_R = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Order cost, ₽", null=True)

    def save(self, *args, **kwargs):
        response = requests.get(f'https://www.cbr.ru/scripts/XML_daily.asp?date_req='
                                f'{datetime.strptime(str(self.time), "%Y-%m-%d").strftime("%d/%m/%Y")}')
        root = ET.fromstring(response.text)
        self.cost_R = float(self.cost) * float(root.findall('.//Valute[@ID="R01235"]/Value')[0].text.replace(',', '.'))
        super(Order, self).save(*args, **kwargs)


class ChannelNotification(models.Model):
    resourceId = models.CharField(max_length=64)
    channelId = models.CharField(max_length=64)
    expiration = models.IntegerField()

    def save(self, *args, **kwargs):
        self.expiration = int(float(self.expiration) / 1000)
        super(ChannelNotification, self).save(*args, **kwargs)
