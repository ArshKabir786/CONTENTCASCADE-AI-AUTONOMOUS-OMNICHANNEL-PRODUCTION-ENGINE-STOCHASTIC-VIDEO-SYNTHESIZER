import sys
import vertexai
from google.oauth2 import service_account
from vertexai.preview.vision_models import ImageGenerationModel

def test():
    try:
        print("Authenticating...")
        credentials = service_account.Credentials.from_service_account_file("/Users/vanshsehrawat/Documents/New project/backend/gcp-credentials.json")
        vertexai.init(project="gen-lang-client-0441766511", location="us-central1", credentials=credentials)
        print("Loading fast model...")
        model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")
        print("Generating image...")
        response = model.generate_images(prompt="A futuristic city", number_of_images=1)
        print("Success! Got response.")
    except Exception as e:
        print("Error:", type(e).__name__, "-", str(e))

if __name__ == "__main__":
    test()
