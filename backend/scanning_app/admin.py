from django.contrib import admin
from .models import ScannedItem
# Register your models here.

@admin.register(ScannedItem)
class ScannedItemAdmin(admin.ModelAdmin):
    list_display = ['scan_data','scan_type','status','timestamp']
    list_filter = ['scan_type','status','timestamp']
    search_fields = ['scan_data']
    readonly_field = ['timestamp']
    list_per_page = 20

    def get_query(self,request):
        return super().get_queryset(request).select_related()
