from django.contrib.auth.models import User
from ..models import UserProfile, ScannedItem, ProductInfo
from .vision_service import DynamicVisionService
from django.utils import timezone
import os
from django.conf import settings
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

class DynamicScanService:

    def __ini__(self):
        self.vision_service = DynamicVisionService()
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
    
    def _process_text_scan(self,user,scan_data,scan_type,metadata):

        try:
            text_analysis = self._analyze_text_dynamically(scan_data)
            
            scan = ScannedItem.objects.create(
                user = user,
                scan_data = scan_data,
                scan_type = scan_type,
                metadata = {
                    **metadata,
                    'text_analysis': text_analysis,
                    'word_count':len(scan_data.split()),
                    'content_type': text_analysis.get('content_type','unknown')
                }
            )

            return {
                'success': True,
                'scan':scan,
                'text_analysis':text_analysis
            }
        except Exception as e:
            logger.error(f"Text scan processing error: {e}")
            return {
                'success': False,
                'error': f'Text processing failed: {str(e)}'
            }
        
    def _lookup_code_dynamically(self,code_data,code_type):

        return {
            'type':code_type,
            'data':code_data,
            'lookup_source': 'internal',
            'timestamp': timezone.now().isoformat()
        }
    
    def _analyze_text_dynamically(self,text_data):

        word_count = len(text_data.split())
        char_count = len(text_data)

        return {
            'word_count': word_count,
            'char_count': char_count,
            'content_type':self._classify_content_type(text_data),
            'language': 'en',
            'readability_score':self._calculate_readability(text_data)
        }
    
    def _classify_content_type(self,text):

        text_lower = text.lower()

        if any(word in text_lower for word in ['price','cost','$','rs']):
            return 'price_information'
        elif any(word in text_lower for word in ['http','www','.com']):
            return 'url'
        elif len(text)<50:
            return 'short_text'
        else:
            return 'general_text'
        
    def _calculate_readability(self,text):
        word = text.split()
        if not word:
            return 0
        
        avg_word_length = sum(len(word) for word in words)/len(words)
        return min(100,max(0,100-(avg_word_length*5)))
    

    def _create_dynamic_product_info(self,object_data):

        product_details = self.vision_service.get_product_details(object_data['name'])

        product_info = productInfo.objects.create(
            name = object_data['name'],
            category = object_data.get('category','other'),
            description = product_details.get('description',''),
            metadata = {
                'common_uses':product_details.get('detailed_info',{}).get('common_uses',[]),
                'fun_fact':product_details.get('detailed_info',{}).get('fun_fact',''),
                'detection_confidence':object_data.get('confidence',0.0),
                'api_source':product_details.get('api_used','unknown'),
                'source_api':object_data.get('api_source','unknown')
            }
        )

        return product_info
    
    def _update_user_stats(self,profile,scan_type):

        profile.scan_count+=1

        if not self._is_user_premium(profile.user):
            profile.free_scan_used +=1

        scan_stats = profile.metadat.get('scan_statistics',{})
        scan_stats[scan_type] = scan_stats

        profile.save()

    def _get_upgrade_url(self,user):

        from django.urls import reverse
        return reverse('subscription-plans')
    
    @staticmethod
    def get_user_stats(user):
        try:
            profile = UserProfile.objects.get(user = user)
            total_scans = ScannedItem.objects.filter(user=user).count()
            object_scans = ScannedItem.objects.filter(user=user,is_object_detected = True).count()

            scan_statistics = profile.metadata.get('scan_statistics',{})
            recent_activity = ScannedItem.objects.filter(
                user = user,
                timestamp__gte = timezone.now() - timedelta(days = 7)
            ).count()

            return {
                'total_scans': total_scans,
                'object_scans': object_scans,
                'free_scans_used': profile.free_scans_used,
                'max_free_scans': profile.max_free_scans,
                'remaining_scans': DynamicScanService.get_remaining_scans(user),
                'is_premium': DynamicScanService._is_user_premium(user),
                'premium_expiry': getattr(profile, 'premium_expiry', None),
                'scan_statistics': scan_statistics,
                'recent_activity': recent_activity,
                'scan_efficiency': round((object_scans / total_scans * 100) if total_scans > 0 else 0, 2)
            }
        except UserProfile.DoesNotExist:
            return None
        