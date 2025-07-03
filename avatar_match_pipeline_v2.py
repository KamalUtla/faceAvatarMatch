import os
import json
import time
import tempfile
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image
import base64
import io
import random

from avatar_service import AvatarService
from in_memory_llm_service import InMemoryLLMService

def create_batches(items: List[Any], batch_size: int = 6) -> List[List[Any]]:
    """Create batches from a list of items"""
    batches = []
    for i in range(0, len(items), batch_size):
        batches.append(items[i:i + batch_size])
    return batches

def image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string"""
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return img_str

def base64_to_image(base64_str: str) -> Image.Image:
    """Convert base64 string back to PIL Image"""
    img_data = base64.b64decode(base64_str)
    return Image.open(io.BytesIO(img_data))

def add_numbered_strip_to_image(image: Image.Image, number: int) -> Image.Image:
    """Add a numbered strip to an image (in-memory version, 60px strip)"""
    img_with_number = image.copy()
    width, height = img_with_number.size
    new_height = height + 60  # Increased strip height
    new_image = Image.new('RGB', (width, new_height), (255, 255, 255))
    new_image.paste(img_with_number, (0, 0))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(new_image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 28)
        except:
            font = ImageFont.load_default()
    text = str(number)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = height + (60 - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), text, fill=(0, 0, 0), font=font)
    return new_image

def add_label_strip_to_image(image: Image.Image, label: str) -> Image.Image:
    """Add a labeled strip to an image (in-memory version, 60px strip)"""
    img_with_label = image.copy()
    width, height = img_with_label.size
    new_height = height + 60
    new_image = Image.new('RGB', (width, new_height), (255, 255, 255))
    new_image.paste(img_with_label, (0, 0))
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(new_image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 28)
        except:
            font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = height + (60 - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), label, fill=(0, 0, 0), font=font)
    return new_image

def process_batch_in_memory(llm_service: InMemoryLLMService, avatar_service: AvatarService, 
                           user_image: Image.Image, batch_avatar_ids: List[str], 
                           avatar_images_cache: Dict[str, Image.Image]) -> Tuple[str, int]:
    """Process a single batch using in-memory images and return the best match avatar ID and its index"""
    batch_images = []
    valid_avatar_ids = []
    for avatar_id in batch_avatar_ids:
        if avatar_id in avatar_images_cache:
            batch_images.append(avatar_images_cache[avatar_id])
            valid_avatar_ids.append(avatar_id)
        else:
            print(f"Warning: Avatar {avatar_id} not found in cache, skipping")
    if not batch_images:
        return batch_avatar_ids[0], 0
    # Randomize avatar images and ids together
    combined = list(zip(batch_images, valid_avatar_ids))
    random.shuffle(combined)
    batch_images, valid_avatar_ids = zip(*combined)
    batch_images = list(batch_images)
    valid_avatar_ids = list(valid_avatar_ids)
    # Add numbered strips to randomized avatar images
    numbered_batch_images = []
    for i, image in enumerate(batch_images, 1):
        numbered_image = add_numbered_strip_to_image(image, i)
        numbered_batch_images.append(numbered_image)
    # Add 'Real Photo' strip to user image
    user_image_with_label = add_label_strip_to_image(user_image, "Real Photo")
    # Get best match from LLM using numbered in-memory images
    best_match_image, winner_index = llm_service.get_best_match_in_batch(user_image_with_label, numbered_batch_images)
    # Map winner index back to correct avatar ID
    winner_avatar_id = valid_avatar_ids[winner_index]
    return winner_avatar_id, winner_index

def find_best_avatar_match_v2(user_image_path: str, batch_size: int = 6) -> Dict[str, Any]:
    """Main pipeline to find the best avatar match using tournament-style elimination with optimized in-memory processing"""
    
    # Initialize services
    llm_service = InMemoryLLMService()
    avatar_service = AvatarService()
    
    # Load user image
    try:
        user_image = Image.open(user_image_path)
        print(f"Loaded user image: {user_image.size}")
    except Exception as e:
        return {"error": f"Failed to load user image: {e}"}
    
    # First, detect gender and child status from user image
    print("Detecting gender and child status from user image...")
    gender_child_info = llm_service.get_gender_child_info_from_image(user_image)
    gender = gender_child_info.get("gender", "unknown")
    is_child = gender_child_info.get("child", "false") == "true"
    
    print(f"Detected: gender={gender}, child={is_child}")
    
    # Filter avatars based on detected characteristics
    age_group = "child" if is_child else "adult"
    
    if gender == "unknown":
        # If gender detection fails, use all avatars of the detected age group
        avatar_ids = avatar_service.get_avatar_ids_by_criteria(age_group=age_group)
        print(f"Gender detection failed, using all {age_group} avatars")
    else:
        # Create filter based on gender and child status
        avatar_ids = avatar_service.get_avatar_ids_by_criteria(gender=gender, age_group=age_group)
        print(f"Filtering avatars: gender={gender}, age_group={age_group}")
    
    if not avatar_ids:
        return {"error": f"No avatar images found matching criteria: gender={gender}, age_group={age_group}"}
    
    print(f"Found {len(avatar_ids)} matching avatars to process")
    print(f"User image: {user_image_path}")
    print(f"Batch size: {batch_size}")
    
    # OPTIMIZATION: Pre-download all filtered avatars once and cache them in memory
    print("Pre-downloading all filtered avatars...")
    start_download_time = time.time()
    
    # Download all images in parallel for better performance
    avatar_images_cache = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all download tasks
        future_to_avatar_id = {}
        for avatar_id in avatar_ids:
            metadata = avatar_service.get_avatar_metadata(avatar_id)
            if metadata and metadata.get('public_url'):
                future_to_avatar_id[executor.submit(avatar_service.download_image_from_url, metadata['public_url'])] = avatar_id
            else:
                print(f"No public URL found for avatar {avatar_id}, skipping")
        
        # Collect results as they complete
        for future in as_completed(future_to_avatar_id):
            avatar_id = future_to_avatar_id[future]
            try:
                image = future.result()
                if image:
                    avatar_images_cache[avatar_id] = image
                    print(f"Downloaded avatar {avatar_id}")
                else:
                    print(f"Failed to download avatar {avatar_id}")
            except Exception as e:
                print(f"Error downloading avatar {avatar_id}: {e}")
    
    download_time = time.time() - start_download_time
    print(f"Downloaded {len(avatar_images_cache)} avatars in {download_time:.2f} seconds")
    
    if not avatar_images_cache:
        return {"error": "Failed to download any avatar images"}
    
    # Tournament-style elimination using cached images
    current_round = 1
    current_candidates = list(avatar_images_cache.keys())  # Use only downloaded avatars
    elimination_history = []
    
    while len(current_candidates) > 1:
        print(f"\n=== ROUND {current_round} ===")
        print(f"Processing {len(current_candidates)} candidates")
        
        # Create batches with specified batch size
        batches = create_batches(current_candidates, batch_size=batch_size)
        print(f"Created {len(batches)} batches of size {batch_size}")
        
        # Process batches in parallel using cached images
        winners = []
        batch_details = []
        with ThreadPoolExecutor(max_workers=min(len(batches), 10)) as executor:
            # Submit all batch processing tasks
            future_to_batch = {
                executor.submit(process_batch_in_memory, llm_service, avatar_service, 
                              user_image, batch, avatar_images_cache): batch 
                for batch in batches
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    winner_id, winner_index = future.result()
                    winners.append(winner_id)
                    batch_details.append({
                        "batch_avatar_ids": batch,
                        "winner_id": winner_id,
                        "winner_index": winner_index
                    })
                    print(f"Batch winner: {winner_id} (index {winner_index})")
                except Exception as e:
                    print(f"Batch processing failed: {e}")
                    # Fallback to first avatar in batch
                    winners.append(batch[0])
                    batch_details.append({
                        "batch_avatar_ids": batch,
                        "winner_id": batch[0],
                        "winner_index": 0
                    })
        
        # Record elimination for this round
        elimination_history.append({
            "round": current_round,
            "candidates": current_candidates,
            "winners": winners,
            "batch_details": batch_details
        })
        
        # Update candidates for next round
        current_candidates = winners
        current_round += 1
        
        # Add delay to avoid rate limiting
        time.sleep(1)
    
    # Final result
    best_match_id = current_candidates[0] if current_candidates else None
    
    # Get metadata for the best match
    best_match_metadata = avatar_service.get_avatar_metadata(best_match_id) if best_match_id else None
    
    result = {
        "best_match": {
            "avatar_id": best_match_id,
            "metadata": best_match_metadata
        },
        "total_rounds": current_round - 1,
        "total_avatars_processed": len(avatar_ids),
        "batch_size": batch_size,
        "elimination_history": elimination_history,
        "user_image_path": user_image_path,
        "user_characteristics": {
            "gender": gender,
            "is_child": is_child,
            "age_group": age_group
        },
        "performance_metrics": {
            "download_time": download_time,
            "avatars_downloaded": len(avatar_images_cache),
            "total_avatars_requested": len(avatar_ids)
        }
    }
    
    print(f"\n=== FINAL RESULT ===")
    print(f"Best match ID: {best_match_id}")
    print(f"Total rounds: {current_round - 1}")
    print(f"Download time: {download_time:.2f}s")
    print(f"Avatars downloaded: {len(avatar_images_cache)}/{len(avatar_ids)}")
    
    return result

def run_avatar_matching_v2(user_image_path: str, batch_size: int = 6) -> Dict[str, Any]:
    """
    Run the new avatar matching pipeline with URL downloads
    
    Args:
        user_image_path: Path to the user's image
        batch_size: Number of avatars to compare at once
        
    Returns:
        Dictionary containing:
        - best_match_avatar_id: ID of the best matching avatar
        - user_image_path: Path to the user's image
        - metadata: Additional information about the matching process
    """
    # Validate inputs
    if not os.path.exists(user_image_path):
        raise FileNotFoundError(f"User image not found: {user_image_path}")
    
    # Run the pipeline
    result = find_best_avatar_match_v2(user_image_path, batch_size)
    
    # Check for errors
    if "error" in result:
        raise RuntimeError(result["error"])
    
    # Return simplified result
    return {
        "best_match_avatar_id": result["best_match"]["avatar_id"],
        "best_match_metadata": result["best_match"]["metadata"],
        "user_image_path": user_image_path,
        "metadata": {
            "total_rounds": result["total_rounds"],
            "total_avatars_processed": result["total_avatars_processed"],
            "batch_size": result["batch_size"]
        },
        "elimination_history": result["elimination_history"],
        "user_characteristics": result["user_characteristics"],
        "performance_metrics": result.get("performance_metrics", {})
    }

def test_pipeline():
    """Test the new pipeline"""
    print("=== Testing New Avatar Matching Pipeline ===")
    
    # Test with a sample image
    test_image_path = "user_test_images/ghibli.jpg"
    
    if not os.path.exists(test_image_path):
        print(f"Test image not found: {test_image_path}")
        return
    
    try:
        # Run the pipeline
        result = run_avatar_matching_v2(test_image_path, batch_size=3)
        
        print(f"\n=== RESULTS ===")
        print(f"Best match avatar ID: {result['best_match_avatar_id']}")
        print(f"Total rounds: {result['metadata']['total_rounds']}")
        print(f"Total avatars processed: {result['metadata']['total_avatars_processed']}")
        print(f"User characteristics: {result['user_characteristics']}")
        
        # Show metadata about the best match
        if result['best_match_metadata']:
            metadata = result['best_match_metadata']
            print(f"\nBest match metadata:")
            print(f"  Gender: {metadata.get('gender', 'N/A')}")
            print(f"  Age group: {metadata.get('age_group', 'N/A')}")
            print(f"  Filename: {metadata.get('filename', 'N/A')}")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline() 