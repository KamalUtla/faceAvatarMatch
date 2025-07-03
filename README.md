# Avatar Matcher - Streamlit App

A smart avatar matching application that uses AI to find the best avatar match for your photo.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd desc_avtr_match
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

4. **Run the Streamlit app**
   ```bash
   streamlit run streamlit_app.py
   ```

## 📁 Essential Files

The following files are required to run the application:

- `streamlit_app.py` - Main Streamlit application
- `avatar_match_pipeline_v2.py` - Optimized avatar matching pipeline
- `avatar_service.py` - Avatar metadata and image download service
- `in_memory_llm_service.py` - LLM service for image analysis
- `avatar_metadata.jsonl` - Avatar metadata database
- `requirements.txt` - Python dependencies
- `user_test_images/ghibli.jpg` - Sample test image

## 🎯 Features

- **Smart Gender & Age Detection**: Automatically detects gender and age group from uploaded photos
- **Optimized Processing**: Pre-downloads avatars once and processes them in memory
- **Tournament-Style Matching**: Uses elimination rounds to find the best match
- **Performance Metrics**: Shows download times and processing statistics
- **Beautiful UI**: Modern, responsive interface with real-time progress tracking

## 🔧 How It Works

1. Upload your photo
2. AI detects your gender and age group
3. System filters avatars based on your characteristics
4. Downloads matching avatars (once, in parallel)
5. Runs tournament-style elimination to find the best match
6. Displays results with performance metrics

## 📊 Performance Optimizations

- **Pre-download Strategy**: All filtered avatars downloaded once at start
- **In-Memory Processing**: No temporary files, direct PIL image processing
- **Image Caching**: Images cached by ID, reused across all rounds
- **Parallel Downloads**: Multiple avatars downloaded simultaneously
- **Numbered Strips**: LLM-friendly image numbering for accurate identification

## 🛠️ Configuration

- **Batch Size**: Adjust the number of avatars compared at once (2-8)
- **API Key**: Set your Gemini API key in the `.env` file

## 📝 License

This project is for educational and research purposes. 