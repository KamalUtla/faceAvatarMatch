import streamlit as st
import os
import tempfile
from PIL import Image
import time
from avatar_match_pipeline_v2 import run_avatar_matching_v2
import base64
import json
import requests
import io

# Page configuration
st.set_page_config(
    page_title="Avatar Matcher",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 2rem;
    }
    .upload-section {
        background-color: #f0f2f6;
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .result-section {
        background-color: #e8f5e8;
        padding: 2rem;
        border-radius: 10px;
        margin-top: 2rem;
    }
    .image-container {
        text-align: center;
        margin: 1rem 0;
    }
    .image-container img {
        max-width: 250px;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .stats-box {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #1f77b4;
        color: #222;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Main header
    st.markdown('<h1 class="main-header">🎯 Smart Avatar Matcher</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem; color: #666;">
        <p>Upload your photo and our AI will automatically detect your gender and age group, then find the best matching avatar from our curated collection!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Main", "Tournament Visualization"]
    )
    
    if page == "Main":
        show_main_page()
    elif page == "Tournament Visualization":
        show_visualization_page()

def show_main_page():
    """Main page with image upload and matching functionality"""
    
    # Upload section
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    st.subheader("📤 Upload Your Image")
    
    uploaded_file = st.file_uploader(
        "Choose an image file",
        type=['png', 'jpg', 'jpeg', 'webp'],
        help="Upload a clear photo of yourself. Our AI will detect your gender and age group to find the most suitable avatars."
    )
    
    # Clear best match if a new file is uploaded
    if 'last_uploaded_filename' not in st.session_state:
        st.session_state.last_uploaded_filename = None
    if uploaded_file is not None and uploaded_file.name != st.session_state.last_uploaded_filename:
        st.session_state.last_result = None
        st.session_state.last_uploaded_filename = uploaded_file.name

    # Batch size slider
    st.subheader("⚙️ Configuration")
    batch_size = st.slider(
        "Batch Size",
        min_value=1,
        max_value=16,
        value=4,
        help="Number of avatars to compare at once. Higher values may be faster but less accurate."
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Process button
    if uploaded_file is not None:
        # Display uploaded image and (if available) best match side by side
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Uploaded Image")
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=250)
        with col2:
            if 'last_result' in st.session_state and st.session_state.last_result is not None and 'best_match_metadata' in st.session_state.last_result:
                metadata = st.session_state.last_result['best_match_metadata']
                public_url = metadata.get('public_url')
                if public_url:
                    try:
                        response = requests.get(public_url, timeout=10)
                        response.raise_for_status()
                        avatar_img = Image.open(io.BytesIO(response.content))
                        st.subheader("Best Match Avatar")
                        st.image(avatar_img, width=250)
                    except Exception as e:
                        st.error(f"Could not load avatar image: {e}")
        # Show processing time below the images if available
        if 'last_result' in st.session_state and st.session_state.last_result is not None and 'best_match_metadata' in st.session_state.last_result and 'last_processing_time' in st.session_state:
            st.markdown(f'<div style="text-align:center; color:#888; margin-top:1rem;">Processing time: {st.session_state.last_processing_time:.2f}s</div>', unsafe_allow_html=True)
        # Process button
        if st.button("🎯 Find Best Avatar Match", type="primary"):
            process_image(uploaded_file, batch_size)

def process_image(uploaded_file, batch_size):
    """Process the uploaded image and find the best avatar match"""
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Start timing
    start_time = time.time()
    
    try:
        # Save uploaded file to temporary location
        status_text.text("Saving uploaded image...")
        progress_bar.progress(10)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
            # Convert to RGB if necessary and save as PNG
            image = Image.open(uploaded_file)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image.save(tmp_file.name, 'PNG')
            temp_image_path = tmp_file.name
        
        status_text.text("Initializing avatar matching...")
        progress_bar.progress(20)
        
        # Run the new avatar matching pipeline
        status_text.text("Processing avatars...")
        progress_bar.progress(40)
        
        result = run_avatar_matching_v2(
            user_image_path=temp_image_path,
            batch_size=batch_size
        )
        
        progress_bar.progress(90)
        status_text.text("Finalizing results...")
        
        # Calculate total time
        end_time = time.time()
        total_time = end_time - start_time
        
        # Store result in session state for main page and visualization page
        st.session_state.last_result = result
        st.session_state.last_processing_time = total_time
        
        progress_bar.progress(100)
        status_text.text(f"✅ Matching complete! (Time: {total_time:.2f}s)")
        
        # Clean up temporary file
        os.unlink(temp_image_path)
        
        # Rerun to update UI and show best match
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Error during processing: {str(e)}")
        progress_bar.progress(0)
        status_text.text("Processing failed")

def show_visualization_page():
    """Page for tournament visualization"""
    
    st.subheader("🏆 Tournament Visualization")
    
    if 'last_result' not in st.session_state:
        st.warning("⚠️ No matching results available. Please run a match on the main page first.")
        return
    
    result = st.session_state.last_result
    
    st.info("This page shows the detailed tournament-style elimination process used to find the best avatar match.")
    
    # Display elimination history
    elimination_history = result.get('elimination_history', [])
    
    if elimination_history:
        for round_data in elimination_history:
            round_num = round_data["round"]
            candidates = round_data["candidates"]
            winners = round_data["winners"]
            
            st.markdown(f"""
            <div class="stats-box">
                <h4>🏆 Round {round_num}</h4>
                <p><strong>Candidates:</strong> {len(candidates)}</p>
                <p><strong>Winners:</strong> {len(winners)}</p>
                <p><strong>Winner IDs:</strong> {', '.join(winners[:5])}{'...' if len(winners) > 5 else ''}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No elimination history available for visualization.")
    
    # Download button for the results
    st.download_button(
        label="📥 Download Results as JSON",
        data=json.dumps(result, indent=2),
        file_name="avatar_match_result.json",
        mime="application/json"
    )

if __name__ == "__main__":
    main() 