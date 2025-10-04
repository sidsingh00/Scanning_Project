from django.shortcuts import render
from rest_framework import generics,status
from rest_framework.decorators import api_view , action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count
from django.utils import timezone
from datetime import datetime,timedelta
from .models import ScannedItem
from .serializers import ScannedItemSerializer,ScannedCreateSerializer,ScanStatsSerializer

# Create your views here.

class ScannedItemListCreateView(generics.ListCreateAPIView):
    queryset = ScannedItem.objects.all()
    serializer_class = ScannedItemSerializer

    def create(self,request,*args,**kwargs):
        serializer = ScannedCreateSerializer(data=request.data)
        if serializer.is_valid():
            scan_item = Scanned_Item.objects.create(**serializer.validated_data)
            data = {
                "scanItem": ScannedItemSerializer(scan_item).data,
                "status": status.HTTP_201_CREATED
            }
            return Response(data)
        
        return Response(serializer.errors,status= status.HTTP_404_BAD_REQUEST)
    
class ScannedItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ScannedItem.objects.all()
    serializer_class = ScannedItemSerializer

@api_view(['POST'])
def bulk_scan_create(request):
    serializer = ScannedCreateSerializer(data = request.data , many = True)
    if serializer.is_valid():
        scan = [ScannedItem(**data) for data in serializer.validated_data]
        ScannedItem.objects.bulk_create(scan)

        return Response(
            {
                "message": f"{len(scan)} scan created"
            },
            status = status.HTTP_201_CREATED
        )
    else:
        return Response(
            serializer.errors,
            status= status.HTTP_400_BAD_REQUEST
        )
    
def upgrade_link():
    # TODO: Implement upgrade link logic or remove if not needed
    pass



@api_view(['GET'])
def scan_stats(request):

    total_scans = ScannedItem.objects.count()

    today = timezone.now().date()
    today_scans = ScannedItem.objects.filter(timestamp_date=today).count()

    if today_scans == 5:
        return Response(
            {
                "message": "limit extended"
            },
            upgrade_link()
        )
    
    scan_type_breakfown = dict(ScannedItem.objects.value_list('scan_type').annotate(
        count = Count('id')
    ).order_by('-count'))

    status_breakdown = dict(ScannedItem.objects.values_list('status').annotate(
        count=Count('id')
    ).order_by('-count'))

    stats = {
        'total_scans' : total_scans,
        'today_scans': today_scans,
        'scan_type_breakdown': scan_type_breakfown,
        'status_breakdown': status_breakdown
    }

    return Response(stats)


@api_view(['GET'])
def recent_scans(request):
    limit = request.GET.get('limit',5)
    scans = ScannedItem.objects.all()[:int(limit)]
    serializer = ScannedItemSerializer(scans,many = True)
    return Response(serializer.data)