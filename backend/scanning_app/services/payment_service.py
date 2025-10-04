import razorpay 
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ..models import Payment,SubscriptionPlan,UserProfile,UserSubscription

class PaymentService:
    def __init__(self):
        self.client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY.KEY_SECRET
        ))

    def create_order(self,user,plan_id):
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)

            order_data = {
                'amount': int(plan.price*100),
                'current':'INR',
                'payment_capture':1,   
                'notes':{
                    'user_id':user.id,
                    'plan_id':plan.id,
                    'plan_name':plan.name
                }   
            }

            order = self.client.order.create(order_data)

            payment = Payment.objects.create(
                user = user,
                subscription_plan = plan,
                razorpay_order_id = order['id'],
                amount = plan.price,
                status = 'pendning'
            )

            return {
                'success':True,
                'order_id':order['id'],
                'amount' : order['amount'],
                'currency':order['currency'],
                'key': settings.RAZORPAY_KEY_ID,
                'payment_id':payment.id
            }
        
        except SubscriptionPlan.DoesNotExist:
            return {'success':False, 'error':'Invalid subscription plan'}
        
        except Exception as e:
            return {'success':False,'error':str(e)}
        

    def verify_payment(self, razorpay_payment_id,razorpay_order_id, razorpay_signature):
        try:
            params_dict = {
                'razorpay_order_id' : razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }

            self.client.utility.verify_payment_signature(params_dict)

            payment = Payment.objects.get(razorpay_order_id= razorpay_order_id)
            payment.razorpay_payment_id = razorpay_payment_id
            payment.status = 'success'
            payment.save()

            self._active_subscription(payment)

            return {
                'success': True,
                'payment': payment
            }
        
        except razorpay.errors.SignatureVerificationError:
            return {'success': False, 'error': 'Invalid payment signature'}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}


    def _active_subscription(self,payment):

        plan = payment.subscription_plan
        user = payment.user

        if plan.plan_type == 'monthly':
            end_date = timezone.now()+ timedelta(days = 30)
        elif plan.plan_type == 'yearly':
            end_date = timezone.now() + timedelta(days = 365)
        else: 
            end_date = timezone.now()+ timedelta(days=365*10)

        subscription = UserSubscription.objects.create(
            user = user,
            subscription_plan = plan,
            payment = payment,
            end_date = end_date,
            is_active = True
        )

        profile = UserProfile.objects.get(user = user)
        profile.is_premium = True
        profile.premium_expiry = end_date
        profile.save()

        return subscription
    
    def get_payment_status(self,payment_id):
        try:
            Payment= Payment.objects.get(id = payment_id)

            return {
                'success':True,
                'status':Payment.status,
                'order_id': Payment.razorpay_order_id
            }
        
        except Payment.DoesNotExist:
            return {
                'success':False,
                'error': 'Payment not found'
            }
    
