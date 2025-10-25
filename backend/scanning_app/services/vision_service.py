import requests
import base64
import json
from django.conf import settings

class VisionService:

    def __init__(self):
        self.api_key = getattr(settings,'IMAGGA_API_KEY','')
        self.api_secret = getattr(settings,'IMAGGA_API_SECRET','')
        self.base_url = "https://api.imagga.com/v2/"

    def detect_object(self,image_path):

        if not self.api_key or not self.api_secret:
            return self._mock_detection()
        
        try:

            with open(image_path,'rb') as image_file:
                image_data = base64.b64encode(image_file.read()).decode()

            headers = {
                'Authorization':f'Basic {base64.b64encode(f"{self.api_key}:{self.api_secret}".encode()).decode()}'
            }

            data = {
                'image_base64' : image_data
            }

            response = requests.post(
                f'{self.base_url}/tags',
                headers= headers,
                data = data
            )

            if response.status_code == 200:
                return self._parse_imagga_response(response.json())
            else:
                return self._mock_detection()
            
        except Exception as e:
            print(f'vision API error: {e}')
            return self._mock_detection()
        
    def _parse_imagga_response(self,response_data):
        