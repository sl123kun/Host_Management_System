from django.contrib import admin
from .models import (
    Host, HostCheckLog, HostCountStatistic,
    HostCredential, HostPasswordRotationLog,
)

admin.site.register(Host)
admin.site.register(HostCredential)
admin.site.register(HostCheckLog)
admin.site.register(HostCountStatistic)
admin.site.register(HostPasswordRotationLog)
