from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.models import User
from django.utils import timezone
from .models import ScannedItem, SubscriptionPlan, Payment, UserSubscription
from .serializers import ScannedItemSerializer, SubscriptionPlanSerializer, PaymentSerializer
from .services.scan_service import ScanService
from .services.payment_service import PaymentService
from .services.subscription_service import SubscriptionService
import json
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




class ScannedItemListCreateView(generics.ListCreateAPIView):
    serializer_class = ScannedItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ScannedItem.objects.filter(user = self.request.user)
    
    def create(self,request,*args,**kwargs):
        scan_data = request.data.get('scan_data')
        scan_type = request.data.get('scan_data','text')
        metadata = request.data.get('metadata',{})

        if not scan_data:
            return Response(
                {
                    'error':'Scan data is required'
                },
                status = status.HTTP_400_BAD_REQUEST
            )
        
        result = ScanService.create.scan(
            user = request.user,
            scan_data = scan_data,
            scan_type = scan_type,
            metadata = metatdat
        )

        if result['success']:
            serializer = ScannedItemSerializer(result['scan'])
            return Response({
                'scan': serializer.data,
                'remaining_scans': result['remaining_scans']
            },status = status.HTTP_201_CREATED)
        else:
            return Response(
                {
                    'error':result['error'],
                    'remaining_scans':result.get('remaining_scans',0)
                },
                status = status.HTTP_402_PAYMENT_REQUIRED
            )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scan_stats(request):
    stats: ScanService.get_user_stats(request.user)
    if stats:
        return Response(stats)
    else:
        return Response(
            {'error':'User stats not found'},
            status = Status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_subscription_status(request):
    subscription = SubscriptionService.get_user_subscription(request.user)
    profile = request.user.userprofile

    response_data = {
        'is_premium': profile.is_premium,
        'premium_expiry': profile.premium_expiry,
        'free_scans_used': profile.free_scans_used,
        'max_free_scans': profile.max_free_scans,
        'remaining_scans':profile.get_remaining_scan(),
        'total_scans': profile.scan_count
    }

    if subscription:
        response_data['subscription'] = {
            'plan_name': subscription.subscription_plan.name,
            'start_date': subscription.start_date,
            'end_date': subscription.end_date
        }

        return Response(response_data)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_plans(request):
    plan = SubscriptionService.get_active_plan()
    serializer = SubscriptionPlanSerializer(plan,many=True)

    return Response({
        'plan':serializer.data,
        'permium_features': SubscriptionService.get_premium_features()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_order(request):
    plan_id = request.data.get('plan_id')

    if not plan_id:
        return Response(
            {'error':'Plan ID is required'},
            status = status.HTTP_400_BAD_REQUEST
        )
    
    payment_service = PaymentService()
    result = payment_service.create_order(request.user,plan_id)

    if result['success']:
        return Response(result)
    else:
        return Response(
            {'error':result['error']},
            status=status.HTTP_400_BAD_REQUEST
        )
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_signature = request.data_get('razorpay_signature')

    if not all([razorpay_order_id,razorpay_payment_id,razorpay_signature]):
        return Response(
            {'error':'Missing payment verification data'},
            status = status.HTTP_400_BAD_REQUEST
        )
    
    payment_service = PaymentService()
    result = payment_service.verify_payment(
        razorpay_payment_id,
        razorpay_order_id,
        razorpay_signature
    )

    if result['success']:
        return Response(
            {
                'success': True,
                'message':'Payment verified and subscription activated',
                'subscription':{
                    'is_premium': True,
                    'expiry':result['payment'].usersubscription.end_date
                }
            }
        )
    else:
        return Response(
            {'error': result['error']}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_status(request,payment_id):

    payment_service = PaymentService()
    result = payment_service.get_payment_status(payment_id)

    if result['success']:
        return Response(result)
    else:
        return Response(
            {'error': result['error']}, 
            status=status.HTTP_404_NOT_FOUND
        )