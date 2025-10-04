from rest_framework import serializers
from .models import ScannedItem

class ScannedItemSerializer(serializers.ModelSerializer):
    class Meta:
        models = ScannedItem
        field = '__all__'
        read_only_fields = ['id','timestamp','image']
    
class ScannedCreateSerializer(serializers.Serializer):

    scan_data = serializers.CharField(max_length=1000)
    scan_type = serializers.ChoiceField(choices=ScannedItem.SCAN_TYPE)
    status = serializers.ChoiceField(choices=ScannedItem.STATUS_CHOICES,default='pending')
    metadata = serializers.JSONField(required=False)
    image = serializers.ImageField()

class ScanStatsSerializer(serializers.Serializer):
    total_scans = serializers.IntegerField()
    today_scans = serializers.IntegerField()
    scan_type_breakdown = serializers.DictField()
    status_breakdown = serializers.DictField()

