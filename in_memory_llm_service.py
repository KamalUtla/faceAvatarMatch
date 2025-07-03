import base64
import os
import re
import json
import io
from typing import List, Dict, Any, Tuple, Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image

# Load environment variables from .env file
load_dotenv()

class InMemoryLLMService:
    """Service class to handle all LLM interactions for avatar matching with in-memory images"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM response service
        
        Args:
            api_key: Optional API key. If not provided, will use GEMINI_API_KEY from environment
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"
    
    def encode_pil_image_to_base64(self, image: Image.Image, format: str = 'JPEG') -> str:
        """Convert PIL Image to base64 string"""
        img_byte_arr = io.BytesIO()
        
        # Convert RGBA to RGB if needed for JPEG
        if image.mode == 'RGBA' and format == 'JPEG':
            # Create a white background
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
            image = rgb_image
        
        image.save(img_byte_arr, format=format)
        img_byte_arr = img_byte_arr.getvalue()
        return base64.b64encode(img_byte_arr).decode('utf-8')
    
    def create_batch_comparison_prompt(self, batch_size: int) -> str:
        """Create the prompt for comparing user image with a batch of avatars"""
        
        prompt = f"""Given the first image (the real person), which image from the remaining {batch_size} images is the best match to it?

Focus on facial features like hair style, facial hair (beard, mustache, stubble), facial accessories (glasses, earrings, piercings), and skin tone also enthnicity (asian/black/brown/white)

Ignore clothing, background, or other non-facial elements.

You must choose one answer. The realism doesn't matter - we are trying to find the best avatar for the first real photo.

IMPORTANT: Number the images starting from 1 (not 0). So the first avatar image is number 1, the second is number 2, and so on up to number {batch_size}.

Respond with ONLY the number (1-{batch_size}) of the best matching image, nothing else."""
        
        return prompt
    
    def create_gender_child_detection_prompt(self) -> str:
        """Create the prompt for detecting gender and child status from an image"""
        
        prompt = """Analyze the person in this image and provide the following information in JSON format:

1. "gender": Determine if the person appears to be "male" or "female" based on facial features, hair style, and other visual cues.

2. "child": Determine if the person appears to be a child (under 18 years old) or an adult. Consider facial features, proportions, and overall appearance.

Respond with ONLY a valid JSON object in this exact format:
{"gender": "male/female", "child": "true/false"}

Do not include any additional text, explanations, or formatting outside the JSON object."""
        
        return prompt
    
    def normalize_boolean_string(self, value: Any) -> str:
        """
        Normalize boolean values to string format
        
        Args:
            value: Any value that might be a boolean
            
        Returns:
            Normalized string "true" or "false"
        """
        if isinstance(value, bool):
            return "true" if value else "false"
        
        if isinstance(value, str):
            # Handle various string representations of boolean
            value_lower = value.lower().strip()
            if value_lower in ["true", "1", "yes", "on"]:
                return "true"
            elif value_lower in ["false", "0", "no", "off"]:
                return "false"
        
        # Default to false for unknown values
        return "false"
    
    def parse_gender_child_response(self, response_text: str) -> Dict[str, str]:
        """
        Parse gender and child information from LLM response
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Dictionary with "gender" and "child" keys as strings
        """
        try:
            # Clean the response text
            cleaned_response = response_text.strip()
            
            # Try to extract JSON from the response
            # Look for JSON-like content between curly braces
            json_match = re.search(r'\{[^}]*\}', cleaned_response)
            if json_match:
                json_str = json_match.group(0)
                parsed_data = json.loads(json_str)
                
                # Normalize the values
                result = {
                    "gender": str(parsed_data.get("gender", "unknown")).lower(),
                    "child": self.normalize_boolean_string(parsed_data.get("child", False))
                }
                
                # Validate gender values
                if result["gender"] not in ["male", "female"]:
                    result["gender"] = "unknown"
                
                print(f"Parsed gender/child data: {result}")
                return result
            else:
                # Fallback parsing if no JSON found
                print("No JSON found in response, attempting fallback parsing")
                return self._fallback_parse_gender_child(response_text)
                
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}, attempting fallback parsing")
            return self._fallback_parse_gender_child(response_text)
        except Exception as e:
            print(f"Error parsing gender/child response: {e}")
            return {"gender": "unknown", "child": "false"}
    
    def _fallback_parse_gender_child(self, response_text: str) -> Dict[str, str]:
        """
        Fallback parsing method for gender and child detection
        
        Args:
            response_text: Raw response text from LLM
            
        Returns:
            Dictionary with "gender" and "child" keys as strings
        """
        response_lower = response_text.lower()
        
        # Parse gender
        gender = "unknown"
        if "male" in response_lower:
            gender = "male"
        elif "female" in response_lower:
            gender = "female"
        
        # Parse child status
        child = "false"
        if any(word in response_lower for word in ["child", "kid", "young", "teen", "teenager", "adolescent"]):
            child = "true"
        elif any(word in response_lower for word in ["adult", "grown", "mature"]):
            child = "false"
        
        result = {"gender": gender, "child": child}
        print(f"Fallback parsed gender/child data: {result}")
        return result
    
    def get_gender_child_info_from_image(self, user_image: Image.Image) -> Dict[str, str]:
        """
        Get gender and child information from a PIL Image
        
        Args:
            user_image: PIL Image object to analyze
            
        Returns:
            Dictionary with "gender" and "child" keys as strings
        """
        try:
            # Create the prompt for gender and child detection
            prompt_text = self.create_gender_child_detection_prompt()
            
            # Get raw LLM response
            response_text = self.get_raw_llm_response(prompt_text, [user_image])
            
            # Parse the response
            result = self.parse_gender_child_response(response_text)
            
            return result
            
        except Exception as e:
            print(f"Error in gender/child detection: {e}")
            # Return default values on error
            return {"gender": "unknown", "child": "false"}
    
    def get_raw_llm_response(self, prompt: str, images: Optional[List[Image.Image]] = None) -> str:
        """
        Get raw LLM response for any prompt with optional PIL images
        
        Args:
            prompt: The text prompt to send to the LLM
            images: Optional list of PIL Image objects to include in the request
            
        Returns:
            Raw text response from the LLM
        """
        try:
            parts = []
            
            # Add images if provided
            if images:
                for img in images:
                    img_base64 = self.encode_pil_image_to_base64(img)
                    parts.append(types.Part.from_bytes(
                        mime_type="image/jpeg",
                        data=base64.b64decode(img_base64),
                    ))
            
            # Add text prompt
            parts.append(types.Part.from_text(text=prompt))
            
            content = types.Content(
                role="user",
                parts=parts
            )
            
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="text/plain",
                thinking_config=types.ThinkingConfig(
                    thinking_budget=0
                )
            )
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=content,
                config=generate_content_config,
            )
            
            # Extract the response text
            response_text = response.text
            if response_text is None:
                raise ValueError("LLM response is empty")
            response_text = response_text.strip()
            print(f"LLM Response: '{response_text}'")
            
            return response_text
            
        except Exception as e:
            print(f"Error getting LLM response: {e}")
            raise
    
    def parse_number_from_response(self, response_text: str, max_number: int) -> int:
        """
        Parse a number from the LLM response
        
        Args:
            response_text: Raw response text from LLM
            max_number: Maximum valid number (batch size)
            
        Returns:
            Parsed number (1-based indexing)
        """
        # Try to extract a number from the response (1 to max_number)
        number_match = re.search(rf'\b([1-{max_number}])\b', response_text)
        if number_match:
            llm_selected_number = int(number_match.group(1))
            print(f"LLM selected number: {llm_selected_number} (1-based)")
            return llm_selected_number
        else:
            # Fallback to first image if no number found
            print(f"No valid number found in response, falling back to first image")
            return 1
    
    def get_best_match_in_batch(self, user_image: Image.Image, batch_images: List[Image.Image]) -> Tuple[Image.Image, int]:
        """
        Get the best matching avatar from a batch of PIL images
        
        Args:
            user_image: PIL Image of the user
            batch_images: List of PIL Image objects of avatars to compare against
            
        Returns:
            Tuple of (selected_image, selected_index) where index is 0-based
        """
        try:
            # Create the prompt for avatar comparison
            prompt_text = self.create_batch_comparison_prompt(len(batch_images))
            
            # Prepare all images (user image first, then batch images)
            all_images = [user_image] + batch_images
            
            # Get raw LLM response
            response_text = self.get_raw_llm_response(prompt_text, all_images)
            
            # Parse the number from response
            llm_selected_number = self.parse_number_from_response(response_text, len(batch_images))
            
            # Convert 1-based to 0-based index
            selected_index = llm_selected_number - 1
            
            if 0 <= selected_index < len(batch_images):
                selected_image = batch_images[selected_index]
                print(f"Selected image at index: {selected_index}")
                return selected_image, selected_index
            else:
                # Fallback to first image if invalid index
                print(f"Invalid index {selected_index}, falling back to first image")
                return batch_images[0], 0
                
        except Exception as e:
            print(f"Error in batch comparison: {e}")
            # Fallback to first image on error
            return batch_images[0], 0

def test_llm_service():
    """Test the in-memory LLM service"""
    from in_memory_avatar_service import InMemoryAvatarService
    
    # Initialize services
    llm_service = InMemoryLLMService()
    avatar_service = InMemoryAvatarService()
    
    print("Testing in-memory LLM service...")
    
    # Get some test avatars
    female_adults = avatar_service.get_avatars_by_criteria(gender='female', age_group='adult')
    if len(female_adults) >= 3:
        test_avatar_ids = [avatar['avatar_id'] for avatar in female_adults[:3]]
        
        # Download images
        avatar_images = avatar_service.download_batch_images(test_avatar_ids)
        
        if len(avatar_images) >= 2:
            # Test gender detection on first image
            first_image = list(avatar_images.values())[0]
            gender_info = llm_service.get_gender_child_info_from_image(first_image)
            print(f"Gender detection result: {gender_info}")
            
            # Test batch comparison
            user_image = first_image  # Use first as user image
            batch_images = list(avatar_images.values())[1:]  # Use rest as batch
            
            if batch_images:
                best_match, index = llm_service.get_best_match_in_batch(user_image, batch_images)
                print(f"Best match found at index: {index}")
        else:
            print("Failed to download enough images for testing")
    else:
        print("Not enough avatars found for testing")

if __name__ == "__main__":
    test_llm_service() 