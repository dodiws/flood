# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flood', '0002_delete_forecastedlastupdate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='forcastedvalue',
            name='basin',
        ),
        migrations.DeleteModel(
            name='Forcastedvalue',
        ),
    ]
