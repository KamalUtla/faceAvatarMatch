import json
import requests
import io
from PIL import Image
from typing import List, Dict, Any, Optional
import os
from pathlib import Path

class AvatarService:
    """Service for managing avatar metadata and downloading images from URLs"""
    
    def __init__(self, metadata_file: str = 'avatar_metadata.jsonl'):
        self.metadata_file = metadata_file
        self.avatars_metadata = self._load_metadata()
        self._image_cache = {}  # Cache for downloaded images
    
    def _load_metadata(self) -> List[Dict[str, Any]]:
        """Load avatar metadata from JSONL file"""
        avatars = []
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                for line in f:
                    if line.strip():
                        avatars.append(json.loads(line.strip()))
        return avatars
    
    def get_avatars_by_criteria(self, gender: Optional[str] = None, age_group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter avatars by gender and age group"""
        filtered_avatars = self.avatars_metadata
        
        if gender and gender != "unknown":
            filtered_avatars = [a for a in filtered_avatars if a.get('gender', '').lower() == gender.lower()]
        
        if age_group:
            filtered_avatars = [a for a in filtered_avatars if a.get('age_group', '').lower() == age_group.lower()]
        
        return filtered_avatars
    
    def get_avatar_ids_by_criteria(self, gender: Optional[str] = None, age_group: Optional[str] = None) -> List[str]:
        """Get avatar IDs filtered by criteria"""
        filtered_avatars = self.get_avatars_by_criteria(gender, age_group)
        return [avatar['avatar_id'] for avatar in filtered_avatars]
    
    def download_image_from_url(self, url: str) -> Optional[Image.Image]:
        """Download image from URL and return PIL Image"""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(response.content))
            return image
            
        except Exception as e:
            print(f"Error downloading image from {url}: {e}")
            return None
    
    def download_batch_images(self, avatar_ids: List[str]) -> Dict[str, Image.Image]:
        """Download multiple images by avatar IDs"""
        downloaded_images = {}
        
        for avatar_id in avatar_ids:
            # Find avatar metadata
            avatar_metadata = next((a for a in self.avatars_metadata if a['avatar_id'] == avatar_id), None)
            
            if not avatar_metadata:
                print(f"Avatar metadata not found for ID: {avatar_id}")
                continue
            
            # Check cache first
            if avatar_id in self._image_cache:
                downloaded_images[avatar_id] = self._image_cache[avatar_id]
                continue
            
            # Download from URL
            url = avatar_metadata.get('public_url')
            if not url:
                print(f"No public URL found for avatar ID: {avatar_id}")
                continue
            
            image = self.download_image_from_url(url)
            if image:
                downloaded_images[avatar_id] = image
                self._image_cache[avatar_id] = image  # Cache the image
            else:
                print(f"Failed to download image for avatar ID: {avatar_id}")
        
        return downloaded_images
    
    def get_avatar_metadata(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific avatar ID"""
        return next((a for a in self.avatars_metadata if a['avatar_id'] == avatar_id), None)
    
    def get_total_avatars(self) -> int:
        """Get total number of avatars"""
        return len(self.avatars_metadata)
    
    def get_avatar_summary(self) -> Dict[str, Any]:
        """Get summary statistics of avatars"""
        gender_counts = {}
        age_counts = {}
        
        for avatar in self.avatars_metadata:
            gender = avatar.get('gender', 'unknown')
            age_group = avatar.get('age_group', 'unknown')
            
            gender_counts[gender] = gender_counts.get(gender, 0) + 1
            age_counts[age_group] = age_counts.get(age_group, 0) + 1
        
        return {
            'total_avatars': len(self.avatars_metadata),
            'gender_distribution': gender_counts,
            'age_group_distribution': age_counts
        }
    
    def clear_cache(self):
        """Clear the image cache"""
        self._image_cache.clear()
    
    def get_cache_size(self) -> int:
        """Get number of cached images"""
        return len(self._image_cache)

def test_avatar_service():
    """Test the avatar service"""
    print("Testing Avatar Service...")
    
    # Initialize service
    service = AvatarService()
    
    # Print summary
    summary = service.get_avatar_summary()
    print(f"Total avatars: {summary['total_avatars']}")
    print(f"Gender distribution: {summary['gender_distribution']}")
    print(f"Age group distribution: {summary['age_group_distribution']}")
    
    # Test filtering
    print("\n=== Testing Filtering ===")
    female_adults = service.get_avatars_by_criteria(gender='female', age_group='adult')
    print(f"Female adults: {len(female_adults)}")
    
    male_children = service.get_avatars_by_criteria(gender='male', age_group='child')
    print(f"Male children: {len(male_children)}")
    
    # Test downloading (just a few for testing)
    if female_adults:
        test_avatar_ids = [avatar['avatar_id'] for avatar in female_adults[:2]]
        print(f"\n=== Testing Download ===")
        print(f"Downloading {len(test_avatar_ids)} images...")
        
        downloaded = service.download_batch_images(test_avatar_ids)
        print(f"Successfully downloaded: {len(downloaded)} images")
        
        for avatar_id, image in downloaded.items():
            print(f"  {avatar_id}: {image.size}")

if __name__ == "__main__":
    test_avatar_service() 