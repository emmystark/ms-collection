# Generated by Django 5.2.3 on 2025-07-13 15:00

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0002_payment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payment',
            name='payment_status',
        ),
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='payment',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
