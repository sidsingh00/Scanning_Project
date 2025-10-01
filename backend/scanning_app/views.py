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
    
