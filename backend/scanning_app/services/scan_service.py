from django.contrib.auth.models import User
from ..models import UserProfile,ScannedItem
from django.utils import timezone

class ScanService:

    @staticmethod
    def can_user_scan(user):
        try:
            profile = UserProfile.objects.get(user = user)
            return profile.can_scan()
        except UserProfile.DoesNotExist:
            return False
        
    @staticmethod
    def get_remaining_scans(user):
        try:
            profile = UserProfile.objects.get(user=user)
            return profile.get_remaining_scans()
        except UserProfile.DoesNotExist:
            return 0
        
    @staticmethod
    def create_scan(user, scan_data, scan_type, metadata = None):
        try:
            profile = UserProfile.objects.get(user=user)

            if not profile.can_scan():
                return {
                    'success': False,
                    'error': 'Scan limit reached. Please upgrade to premium.',
                    'remaining_scans': profile.get_remaining_scans()
                }
            
            scan = ScannedItem.objects.create(user=user,scan_data=scan_data,scan_type=scan_type,metadata=metadata or {})

            profile.increment_scan_count()

            return{
                'success':True,
                'scan':scan,
                'remaining_scan':profile.get_remaining_scans()
            }
        
        except UserProfile.DoesNotExist:
            return{
                'success': False,
                'error': 'User profile not found'
            }
    
    @staticmethod
    def get_user_static(user):
        try:
            profile = UserProfile.objects.get(user=user)
            total_scans = ScannedItem.objects.filter(user=user).count()

            return{
                'total_scans': total_scans,
                'free_scans_used': profile.free_scans_used,
                'max_free_scans': profile.max_free_scans,
                'remaining_scans': profile.get_remaining_scans(),
                'is_premium': profile.is_premium,
                'premium_expiry': profile.premium_expiry
            }
        except UserProfile.DoesNotExist:
            return None