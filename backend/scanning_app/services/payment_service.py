import razorpay
import requests
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ..models import Payment, SubscriptionPlan,UserProfile,UserSubscription
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

class DynamicPaymentService:
    def __init__(self):
        self.client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        ))
        self.payment_gateways = self._initialize_payment_gateways()

    def _initialize_payment_gateways(self):

        gateways = [
            {
                'name':'Razorpay',
                'enabled':bool(settings.RAZORPAY_KEY_ID),
                'priority':1,
                'config': {
                    'key_id':settings.RAZORPAY_KEY_ID,
                    'key_secret':settings.RAZORPAY_KEY_SECRET
                }
            }
        ]

        if hasattr(settings,'STRIPE_SECRET_KEY'):
             gateways.append({
                'name': 'Stripe',
                'enabled': True,
                'priority': 2,
                'config': {'secret_key': settings.STRIPE_SECRET_KEY}
            })
             
        return sorted([g for g in gateways if g['enabled']],key=lambda x:x['priority'])
    
    def create_order(self,user,plan_id,payment_method='razorpay'):
        try:
            plan = SubscriptionPlan.objects.get(id= plan_id,is_active = True)

            gateway = self._select_payment_gateway(payment_method)

            if not gateway:
                return {
                    'success':False,
                    'error':'No payment gateway available'
                }
            
            if gateway['name'] == 'Razorpay':
                return self._create_razorpay_order(user,plan)
            elif gateway['name'] == 'Stripe':
                return self._create_stripe_order(user,plan)
            else:
                return {
                    'success':False,
                    'error':'Unsupported payment method'
                }
            
        except SubscriptionPlan.DoesNotExist:
            return {'success': False, 'error': 'Invalid subscription plan'} 
        
        except Exception as e:
            logger.error(f"Order creation error: {e}")
            return {'success': False, 'error': str(e)}

    def _select_payment_gateway(self,payment_method):

        for gateway in self._payment_gateways:
            if gateway['name'].lower() == payment_method.lower():
                return gateway
            
        return self._payment_gateway[0] if self.payment_gateways else None
    
    def _create_razorpay_order(self,plan,user):

        try:
            order_data = self._generate_order_data(user,plan)

            order = self._client.order_create(order_data)

            payment = self._create_payemnt_record(user,plan,order,'razorpay')

            return {
                'success':True,
                'order_id':order['id'],
                'amount': order['amount'],
                'currency':order['currency'],
                'key':settings.RAZORPAY_KEY_ID,
                'payment_id':payment.id,
                'gateway':'razorpay',
                'order_data':self._sanitize_order_data(order)
            }
        except Exception as e:
            logger.error(f"Razorpay order creation error: {e}")
            return {'success': False, 'error': f'Payment gateway error: {str(e)}'}
        
    def _generate_order_data(self,user,plan):

        base_data = {
            'amount':int(plan.price*100),
            'current':'INR',
            'payment_capture':1,
                'notes': {
                'user_id': user.id,
                'user_email': user.email,
                'plan_id': plan.id,
                'plan_name': plan.name,
                'plan_type': plan.plan_type,
                'timestamp': timezone.now().isoformat()
            }
        }

        if plan.plan_type == 'lifetime':
            base_data['notes']['lifetime_access'] = True
        elif plan.plan_type == 'yearly':
            base_data['notes']['annual_discount'] = self._calculate_discount(plan)

        return base_data
    
    def _calculate_discount(user,self,plan):

        if plan.plan_type == 'yearly':
            monthly_equivalent = plan.price/12
            standard_monthly = 299
            if monthly_equivalent < standard_monthly:
                discount = ((standard_monthly - monthly_equivalent)/standard_monthly) *100
                return round(discount,1)
        return 0
    
    def _create_payment_record(self,user,plan,order_data,gateway):

        return Payment.objects.create(
            user = user,
            subscription_plan = plan,
            razorpay_order_id = order_data['id'],
            amount = plan.price,
            status = 'pending',
            metadata = {
                'gateway':gateway,
                'currency': order_data.get('currency','INR'),
                'order_data': self._sanitize_order_data(order_data),
                'created_at': order_data.get('created_at', timezone.now().isoformat())
            }
        )

    def verify_payment(self,verification_data):

        gateway = verification_data.get('gateway','razorpay')

        if gateway == 'razorpay':
            return self._verify_razorpay_payment(verification_data)
        
        elif gateway == 'stripe':
            return self._verify_stripe_payment(verification_data)
        else:
            return {'success': False, 'error': 'Unsupported payment gateway'}
        
    def _verify_razorpay_payment(self,verification_data):

        try:
            razorpay_payment_id = verification_data.get('razorpay_payment_id')

            razorpay_order_id = verification_data.get('razorpay_order_id')
            razorpay_signature = verification_data.get('razorpay_signature')

            if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
                return {'success': False, 'error': 'Missing verification data'}
                
            param_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id':razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }

            self.client.utility.verify_payment_signature(param_dict)

            Payment_data = self.client.payment_fetch(razorpay_payment_id)

            payment = Payment.objects.get(razorpay_payment_id = razorpay_payment_id)
            payment.razorpay_payment_id = razorpay_payment_id

            payment.status = 'success'
            payment.metadata.update({
                'razorpay_payment_data': self._sanitize_payment_data(Payment_data),
                'verified_at': timezone.now().isoformat(),
                'payment_method': Payment_data.get('method','card')
            })
            payment.save()

            subscription = self._activate_subscription(payment)
            
            return {
                'success': True,
                'payment': payment,
                'subscription': subscription,
                'message': 'Payment verified successfully'
            }
            
        except Payment.DoesNotExist:
            return {'success': False, 'error': 'Payment record not found'}
        except razorpay.errors.SignatureVerificationError:
            return {'success': False, 'error': 'Invalid payment signature'}
        except Exception as e:
            logger.error(f"Payment verification error: {e}")