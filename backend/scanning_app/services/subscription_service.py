from django.utils import timezone
from ..models import UserProfile, UserSubscription , SubscriptionPlan

class SubscriptoinService:
    @staticmethod
    def get_active_plan():
        return SubscriptionPlan.object.filter(is_active=True)
    
    @staticmethod
    def get_user_subscription(user): 
            if(user):
                 
                subscription = UserSubscription.objects.filter(
                    user=user, 
                    is_active=True,
                    end_date__gt=timezone.now()
                ).first()
                return subscription
            return None
    
    
    @staticmethod
    def check_subscription_expiry():
        expired_subscription = UserSubscription.objects.filter(
            is_active = True,
            end_date__lte = timezone.now()
        )

        for subscription in expired_subscription:
            subscription.is_active = False
            subscription.save()

            profile = UserProfile.objects.get(user= subscription.user)
            profile.is_premium = False
            profile.premium_expiry = None
            profile.save()

    @staticmethod
    def get_premium_features():
         return [
              "Unlimited scans",
              "Priority processing",
              "Advanced analytics",
              "Export capabilities",
              "No watermarks",
              "Priority suppport"
         ]