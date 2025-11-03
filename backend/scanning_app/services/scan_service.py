from django.contrib.auth.models import User
from ..models import UserProfile,ScannedItem
from django.utils import timezone
import tempfile
from django.core.files.storage import FileSystemStorage

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

    def _process_image_scan(self,user,scan_data,image,metadata):
        
        try:
            fs = FileSystemStorage(location = tempfile.gettempdir())

            filename = fs.save(image.name,image)
            temp_image_path = fs.path(filename)

            detection_result = self.vision_service.detect_objects(temp_image_path)

            scan = ScannedItem.objects.create(
                user = user,
                scan_type = 'image',
                scan_data = scan_data,
                metadata = {
                    **metadata,
                    'detection_result':detection_result,
                    'original_image_name':image.name
                },
                image= image
            )

            detected_objects = []

            if detection_result.get('success'):
                detected_objects = detection_result.get('objects',[])
                scan.object_labels = detected_objects
                scan.is_object_detected = len(detected_objects)>0

                if detected_objects:
                    main_object = detected_objects[0]
                    product_info = self._create_dynamic_product_info(main_object)
                    scan.product_info = product_info
                
            scan.save()

            fs.delete(filename)

            return {
                'success':True,
                'scan':scan,
                'detected_objects':detected_objects,
                'api_used':detection_result.get('api_used','unknown')
            }

        except Exception as e:
            logger.error(f"Image scan processing error: {e}")
            return {
                'success': False,
                'error': f'Image processing failed: {str(e)}'
            }
        
    def _process_code_scan(self,user,scan_data,scan_type,metatdata):

        try:
            product_info = self._lookup_product_info(scan_data,scan_type)

            scan = ScannedItem.objects.create(
                user = user,
                scan_type = scan_type,
                scan_data = scan_data,
                metadata = {
                    **metadata,
                    'lookup_result':product_info,
                    'code_type': scan_type
                }
            )

            return {
                'success':True,
                'scan':scan,
                'product_info': product_info
            }
        
        except Exception as e:
            logger.error(f"Code scan processing error: {e}")
            return {
                'success': False,
                'error': f'Code processing failed: {str(e)}'
            }
    