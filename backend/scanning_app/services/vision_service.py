import requests
import base64
import json
from django.conf import settings
from datetime import datetime,timedelta
import logging

logger = logging.getLogger(__name__)


class VisionService:

    def __init__(self):
        
        self.apis = self._initialize_apis()
        self.cache = {}
        self.cache_timeout = timedelta(hours=1)


        
    def _initialize_apis(self):

        return [
            {
                'name':'Imagga',
                'function':self._detect_with_imagga,
                'priority':1,
                'enabled':bool(getattr(settings,'IMAGGA_API_KEY',''))
            },
            {
                'name':'GoogleVision',
                'function':self._detect_with_google_vision,
                'priority':2,
                'enabled':bool(getattr(settings,'GOOGLE_VISION_API_KEY',''))
            },
            {
                'name':'Clarifai',
                'function':self._detect_with_clarifai,
                'priority':3,
                'enabled':bool(getattr(settings,'CLARIFAI_API_KEY',''))
            },
            {
                'name':'Fallback',
                'function':self._fallback_detection,
                'priority':99,
                'enabled':True
            },
            {
                'name':'Gemini',
                'function':self._detect_with_gemini,
                'priority':4,
                'enabled':bool(getattr(settings,'GEMINI_API_KEY','') and getattr(settings,'GEMINI_MODEL_NAME',''))
            },
            {
                'name':'OpenA1',
                'function':self._detect_with_openai,
                'priority':5,
                'enabled':bool(getattr(settings,'OPENA1_API_KEY','')) and bool(getattr(settings,'OPENA1_MODEL_NAME',''))
            }
        ]
    

    
    def detect_objects(self,image_path):
        
        cache_key = f"detect_{hash(image_path)}"
        cached_result = self._get_cached(cache_key)
        if cached_result:
            return cached_result
        
        enabled_apis = sorted(
            [api for api in self.apis if api['enabled']],
            key = lambda x:x['priority']
        )

        for api in enabled_apis:
            try:
                logger.info(f"Trying {api['name']}API....")
                result = api['function'](image_path)
                if result and result.get('success',False):
                    self._set_cached(cache_key,result)
                    return result
            except Exception as e:
                logger.warning(f"API {api['name']} API failed: {str(e)}")
                continue
        
        return self._get_fallback_result()
    

    
    def _detect_with_imagga(self,image_path):
        # Implementation for Imagga API
        
        try:
            with open(image_path,'rb') as image_file:
                image_datas = base64.b64encode(image_file.read()).decode()

                headers = {
                    'Authorization':f'Basic{base64.b64encode(f"{settings.IMAGGA_API_KEY}:{settings.IMAGGA_API_SECRET}").encode().decode()}'   
                }


                response = request.post(
                    'https://api.imagga.com/v2/tags',
                    headers= headers,
                    data = {'image_base64':image_datas},
                    timeout = 10
                )


                if response.status_code == 200:
                    data = response.json()
                    objects = self._parse_imagga_response(data)
                    return {
                        'success':True,
                        'objects':objects,
                        'source':'Imagga',
                        'api_used':'Imagga',
                        'confidence': self._calculate_overall_confidence(objects)
                    }

        except Exception as e:
            logger.erro(f"Imagga API error:{e}")

        return {'success':False}
    
    def _detect_with_google_vision(self,image_path):

        try:
            with open(image_path,'rb') as image_file:
                image_content = base64.b64encode(image_file.read()).decode()

                payload = {
                    'requests':[
                        {
                            'image':{
                                'content':image_content
                            },
                            'features':[
                                {
                                    'type':'LABEL_DETECTION',
                                    'maxResults':10
                                }
                            ]
                        }
                    ]
                }


                response = requests.post(
                    f'https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}',
                    json = payload,
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    objects= self._parse_google_vision_response(data)
                    return {
                        'success':True,
                        'objects':objects,
                        'source':'Google Vision',
                        'api_used':'Google Vision',
                        'confidence': self._calculate_overall_confidence(objects)
                    }
        except Exception as e:
            logger.error(f"Google Vision API error: {e}")
        
        return {'success': False}
    

    def _detect_with_clarifai(self,image_path):

        try:
            with open(image_path,'rb') as image_file:
                image_content = base64.b64encode(image_file.read()).decode()

                headers = {
                    'Authorization':f'Key {setting.CLARIFAI_API_KEY}',
                    'Content-Type':'application/json'
                }

                data = {
                    'inputs':[
                        {
                            'data':{
                                'image':{
                                    'base64':image_content
                                }
                            }
                        }
                    ]
                }

                response = request.post(
                    'https://api.clarifai.com/v2/models/general-image-recognition/outputs',
                    headers = headers,
                    json = data,
                    timeout = 10
                )



                if response.status_code == 200:
                    data = response.json()
                    objects = self._parse_clarifai_response(data)
                    return {
                        'success':True,
                        'objects':objects,
                        'source':'Clarifai',
                        'api_used':'Clarifai',
                        'confidence': self._calculate_overall_confidence(objects)
                    }
                
        except Exception as e:
            logger.error(f"Clarifai API error: {e}")
        
        return {'success': False}


    def _detect_with_gemini(self,image_path):

        try:
            with open(image_path,'rb+') as image_file:
                image_content = base64.b64encode(image_file.read()).decode()

                headers = {
                    'Authorization':f'Bearer {settings.GEMINI_API_KEY}',
                    'Content-Type':'application/json'
                }  

                data = {
                    'model':settings.GEMINI_MODEL_NAME,
                    'inputs':{
                        'image':{
                            'base64':image_content
                        }
                    }
                }

                response = request.post(
                    'https://api.gemini.com/v1/models/detect',
                    headers = headers,
                    json = data,
                    timeout = 10
                )

                if response.status_code == 200:
                    data = response.json()
                    objects = self._parse_gemini_response(data)
                    return {
                        'success':True,
                        'objects':objects,
                        'source':'Gemini',
                        'api_used':'Gemini',
                        'confidence': self._calculate_overall_confidence(objects)
                    }
                
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
        
        return {'success': False}


    def _detect_with_openai(self,image_path):

        try:
            with open(image_path,'rb') as image_file:
                image_content = base64.b64encode(image_file.read()).decode()

                headers = {
                    'Authorization': f'Bearer {settings.OPENA1_API_KEY}',
                    'Content-Type':'application/json'
                }

                data = {
                    'inputs':{
                        'image':{
                            'base64':image_content
                        }
                    }
                }

                response = requests.post(
                    'https://api.openai.com/v1/models/detect',
                    headers = headers,
                    json = data,
                    timeout = 10
                )

                if response.status_code == 200:
                    data = response.json()
                    objects = self._parse_openai_response(data)
                    return {
                        'success':True,
                        'objects':objects,
                        'source':'OpenAI',
                        'api_used':'OpenAI',
                        'confidence':self._calculate_overall_confidence(objects)
                    }
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")

        return {'success': False}


    def _parse_imagga_response(self,data):

        objects = []
        if 'result' in data and 'tags' in data['result']:
            for tag in data['result']['tags']:
                if tag['confidence'] > 20:
                    objects.append({
                        'name': tag['tag']['en'],                            
                        'confidence': tag['confidence'],
                        'category': self._dynamic_categorize(tag['tag']['en']),
                        'api_source':'Imagga'
                        })
        return objects[:8]
    

    def _parse_google_vision_response(self,data):

        objects = []
        if 'responses' in data and data['responses']:
            for label in data['responses'][0].get('labelAnnotations',[]):
                objects.append({
                    'name':label['description'],
                    'confidence':label['score']*100,
                    'category':self._dynamic_categorize(label['description']),
                    'api_source':'Google Vision'
                })
        return objects[:8]
    

    def _parse_clarifai_response(self,data):

        objects = []
        if 'outputs' in data and data['outputs']:
            for concept in data['outputs'][0]['data']['concepts']:
                objects.append({
                    'name':concept['name'],
                    'confidence':concept['score']*100,
                    'category':self._dynamic_categorize(concept['name']),
                    'api_source':'Clarifai'
                })
        return objects[:8]
    
    def _parse_gemini_response(self,data):

        objects = []
        if 'predictions' in data and data['predictions']:
            for item in data['predictions']:
                if item['confidence'] > 20:
                    objects.append({
                        'name':item['label'],
                        'confidence':item['confidence'],
                        'category':self._dynamic_categorize(item['label']),
                        'api_source':'Gemini'
                    })
        return objects[:8]
    
    def _parse_openai_response(self,data):

        objects = []
        if 'predictions' in data and data['predictions']:
            for item in data['predictions']:
                if item['confidence']>20:
                    objects.append({
                        'name':item['label'],
                        'confidence':item['confidence'],
                        'category':self._dynamic_categorize(item['label']),
                        'api_source':'OpenAI'
                    })
        return objects[:8]


    def _dynamic_categorize(self,label):

        api_category = self._get_category_from_api(object_name)
        if api_category:
            return api_category
    
        return self._local_categorization(object_name)
    
    def _get_category_from_api(self,label):

        try:
            response = requests.get(
                f"https://api.datamuse.com/words?sp={object_name}&md=d&max=1",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and 'defs' in data[0]:
                    definition = data[0]['defs'][0]
                    return self._extract_category_from_definition(definition)
        except Exception as e:
            logger.error(f"Error fetching category from API: {e}")
        return None
    

    def _extract_category_from_definition(self,definition):

        definition = definition.lower()
        category_keywords = {
            'food': ['food', 'fruit', 'vegetable', 'nutrient', 'edible'],
            'animal': ['animal', 'mammal', 'bird', 'insect', 'species'],
            'tool': ['tool', 'instrument', 'device', 'implement'],
            'vehicle': ['vehicle', 'car', 'transport', 'machine'],
            'clothing': ['clothing', 'garment', 'wear', 'apparel'],
            'furniture': ['furniture', 'furnishing', 'seat', 'table'],
            'electronics': ['electronic', 'device', 'computer', 'digital'],
            'nature': ['plant', 'tree', 'flower', 'landscape', 'natural']
        }