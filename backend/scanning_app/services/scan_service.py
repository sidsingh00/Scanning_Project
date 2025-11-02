from django.contrib.auth.models import User
from ..models import UserProfile,ScannedItem
from django.utils import timezone

logger = loggin.getLogger(__name__)

class DynamicScanService:

    def __ini__(self):
        self.vission_service = DynamicVisionService()
        self.scan_limit = _load_dynamic_limit()

    def _load_dynamic_limit(self):

        return {
            'free_scan': 5,
            'premium_scans':'unlimited',
            'scan_timeout':timeout(minutes=1)
        }


    def can_user_scan(self,user):

        try:
            profile = UserProfile.objects.get(user=user)

            if hasattr(user, 'usersubscription'):
                active_subs = user.usersubscription_set.filter(
                    is_active=True,
                    start_date_lte= timezone.now(),
                    end_date_gt = timezone.now()
                )
                if active_subs.exists():
                    return True
            
            return profile.free_scans_used< profile.max_free_scans
        
        except UserProfile.DoesNotExist:
            return False
    

    def get_remaining_scans(self,user):

        try:
            profile = UserProfile.objects.get(user=user)

            if DynamicScanService._is_user_premium(user):
                return 'unlimited'
            
            return max(0,profile.max_free_scans - profile.free_scans_used)
        
        except UserProfile.DoesNotExist:
            return 0
        
    def _is_user_premium(self,user):

        profile = UserProfile.objects.get(user=user)

        try:
            from ..models import UserSubscription
            return UserSubscription.objects.filter(
                user = user,
                is_active = True,
                end_date_gt = timezone.now()
            ).exists()
        
        except Exception:
            return False
    
    def create_scan(self,user,scan_data,scan_type,metadata=None,image=None):

        try:
            profile = UserProfile.objects.get(user = user)

            if not self.can_user_scan(user):
                return {
                    'success':False,
                    'error':'Scan limit reached. Please upgrade to premium.',
                    'remaining_scans': self.get_remaining_scans,
                    'upgrade_url':self._get_upgrade_url(user)
                }
            
            scan_result = self._process_scan_dynamically(
                user,scan_data,scan_type,metadata,image
            )

            if scan_result['success']:
                self._update_user_stats(profile,scan_type)

                return {
                    'success': True,
                    'scan':scan_result['scan'],
                    'remaining_scans':self.get_remaining_scans(user),
                    'detected_obkects':scan_result.get('detected_objects',[]),
                    'processing_time':scan_result.get('processing_time',0),
                    'api_used':scan_result.get('api_used','local')
                }
            else:
                return {
                    'success':False,
                    'error':scan_result.get('error','Unknown error occurred during scan.'),
                    'remaining_scans':self.get_remaining_scans(user)
                }
        
        except UserProfile.DoesNotExist:
            return {
                'success':False,
                'error':'User profile not found'
            }
        
    def _process_scan_dynamically(self,user,scan_data,scan_type,metadata,image):

        start_time = timezone.now()

        try:
            if scan_type == 'image' and image:
                return self._process_image_scan(user,scan_data,image,metadata)
            elif scan_type in ['barcode','qr']:
                return self._process_code_scan(user,scan_data,image,metadata)
            else:
                return self._process_text_scan(user,scan_data,scan_type,metadata)
            
        except Exception as e:
            logger.error(f"Scan processing error:{e}")
            return {
                'success':False,
                'error': f'Processing failed: {str(e)}'
            }
        
        finally:
            process_time = (timezone.now() - start_time).total_seconds()
            logger.info(f"Scan processing took{process_time:.2f} seconds")