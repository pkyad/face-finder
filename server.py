#!/usr/bin/env python3
"""
FastAPI Face Recognition Server with Streaming Results, Image Upload, and Auto-Resizing
Features: Image upload with auto-resizing, listing, and streaming face recognition.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import face_recognition
import numpy as np
import os
import asyncio
import shutil
from PIL import Image, ImageOps
import io

app = FastAPI(title="Face Recognition Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ImageResizer:
    """Image resizer for optimizing images for face recognition."""
    
    def __init__(self, target_size_kb: int = 500, max_dimension: int = 1920, quality: int = 85):
        """
        Initialize image resizer with compression settings.
        
        Args:
            target_size_kb: Target file size in KB (default: 500KB)
            max_dimension: Maximum width or height in pixels (default: 1920px)
            quality: JPEG quality for compression (default: 85, range: 1-100)
        """
        self.target_size_kb = target_size_kb
        self.max_dimension = max_dimension
        self.quality = quality
        self.target_size_bytes = target_size_kb * 1024
    
    def format_size(self, size_bytes: int) -> str:
        """Format size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
    
    def calculate_optimal_dimensions(self, width: int, height: int) -> tuple:
        """
        Calculate optimal dimensions while maintaining aspect ratio.
        
        Args:
            width: Original width
            height: Original height
            
        Returns:
            Tuple of (new_width, new_height)
        """
        if max(width, height) <= self.max_dimension:
            return width, height
        
        if width > height:
            scale_factor = self.max_dimension / width
        else:
            scale_factor = self.max_dimension / height
        
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        return new_width, new_height
    
    def resize_image_bytes(self, image_bytes: bytes, filename: str) -> dict:
        """
        Resize image from bytes and return result.
        
        Args:
            image_bytes: Image file content as bytes
            filename: Original filename
            
        Returns:
            Dictionary with resizing info and processed image bytes
        """
        try:
            original_size = len(image_bytes)
            
            # Open image from bytes
            img = Image.open(io.BytesIO(image_bytes))
            original_width, original_height = img.size
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Auto-rotate based on EXIF data
            img = ImageOps.exif_transpose(img)
            
            # Calculate optimal dimensions
            new_width, new_height = self.calculate_optimal_dimensions(img.width, img.height)
            
            # Resize if needed
            if (new_width, new_height) != (img.width, img.height):
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes with quality optimization
            current_quality = self.quality
            output_buffer = io.BytesIO()
            img.save(output_buffer, 'JPEG', quality=current_quality, optimize=True)
            final_bytes = output_buffer.getvalue()
            
            # Reduce quality if too large
            attempts = 0
            max_attempts = 10
            
            while len(final_bytes) > self.target_size_bytes and current_quality > 30 and attempts < max_attempts:
                current_quality -= 5
                output_buffer = io.BytesIO()
                img.save(output_buffer, 'JPEG', quality=current_quality, optimize=True)
                final_bytes = output_buffer.getvalue()
                attempts += 1
            
            final_size = len(final_bytes)
            compression_ratio = ((original_size - final_size) / original_size) * 100
            
            return {
                'success': True,
                'original_size': original_size,
                'final_size': final_size,
                'original_dimensions': (original_width, original_height),
                'final_dimensions': (new_width, new_height),
                'compression_ratio': compression_ratio,
                'final_quality': current_quality,
                'image_bytes': final_bytes
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'original_size': len(image_bytes)
            }


class FaceSearcher:
    """Face recognition searcher with streaming results."""
    
    def __init__(self, tolerance: float = 0.6, min_confidence: float = 55.0):
        """
        Initialize face searcher.
        
        Args:
            tolerance: Face comparison tolerance (default: 0.6)
            min_confidence: Minimum confidence percentage (default: 55.0)
        """
        self.tolerance = tolerance
        self.min_confidence = min_confidence
        self.reference_encoding = None
    
    async def stream_search(self, album_folder: str):
        """
        Generator that yields matches as they are found.
        Streams filename and confidence as soon as a match is detected.
        
        Args:
            album_folder: Path to album folder to search
            
        Yields:
            Server-sent event strings with match information
        """
        if self.reference_encoding is None:
            yield "error: No reference face loaded\n\n"
            return
        
        if not os.path.exists(album_folder):
            yield f"error: Album folder not found: {album_folder}\n\n"
            return
        
        # Get all image files
        image_files = []
        for filename in os.listdir(album_folder):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_files.append(os.path.join(album_folder, filename))
        
        if not image_files:
            yield f"error: No image files found in {album_folder}\n\n"
            return
        
        yield f"data: Searching in {len(image_files)} images...\n\n"
        await asyncio.sleep(0.1)
        
        match_count = 0
        
        for image_path in image_files:
            filename = os.path.basename(image_path)
            
            try:
                # Load image and find faces
                image = face_recognition.load_image_file(image_path)
                face_locations = face_recognition.face_locations(image)
                face_encodings = face_recognition.face_encodings(image, face_locations)
                
                # Check each face against reference
                for i, face_encoding in enumerate(face_encodings):
                    face_distance = face_recognition.face_distance(
                        [self.reference_encoding], face_encoding
                    )[0]
                    confidence = (1 - face_distance) * 100
                    
                    # Stream match immediately
                    if face_distance <= self.tolerance and confidence >= self.min_confidence:
                        match_count += 1
                        result = f"✅ MATCH {match_count}: {filename} | Confidence: {confidence:.1f}%"
                        yield f"data: {result}\n\n"
                        await asyncio.sleep(0.05)
                
            except Exception as e:
                error_msg = f"⚠️ Error processing {filename}: {str(e)}"
                yield f"data: {error_msg}\n\n"
                continue
        
        # Final summary
        summary = f"\n🎯 Search Complete! Total matches: {match_count}"
        yield f"data: {summary}\n\n"


# Initialize searcher and resizer
searcher = FaceSearcher()
resizer = ImageResizer(target_size_kb=500, max_dimension=1920, quality=85)


def ensure_folder_exists(folder_path: str):
    """Create folder if it doesn't exist."""
    os.makedirs(folder_path, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Create necessary folders on startup."""
    ensure_folder_exists("albums")
    ensure_folder_exists("static")
    print("✅ Server started - Albums and static folders ready")


@app.post("/upload")
async def upload_image(folder_name: str = Form(...), image: UploadFile = File(...)):
    """
    Upload an image to a specific album folder with automatic resizing.
    
    Args:
        folder_name: Name of the album folder
        image: Image file to upload
    
    Returns:
        Success message with image path and resizing info
    """
    # Validate folder name
    if ".." in folder_name or folder_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    
    # Validate file
    if not image.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if not image.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="Only JPG, JPEG, and PNG files are allowed")
    
    try:
        # Create folder if it doesn't exist
        folder_path = os.path.join("albums", folder_name)
        ensure_folder_exists(folder_path)
        
        # Read image content
        content = await image.read()
        
        # Resize image
        resize_result = resizer.resize_image_bytes(content, image.filename)
        
        if not resize_result['success']:
            raise HTTPException(status_code=400, detail=f"Error resizing image: {resize_result['error']}")
        
        # Save resized image as JPG
        output_filename = os.path.splitext(image.filename)[0] + '.jpg'
        file_path = os.path.join(folder_path, output_filename)
        
        with open(file_path, "wb") as f:
            f.write(resize_result['image_bytes'])
        
        return {
            "status": "success",
            "message": "Image uploaded and resized successfully",
            "folder": folder_name,
            "filename": output_filename,
            "path": file_path,
            "resizing": {
                "original_size": resizer.format_size(resize_result['original_size']),
                "final_size": resizer.format_size(resize_result['final_size']),
                "compression": f"{resize_result['compression_ratio']:.1f}%",
                "original_dimensions": f"{resize_result['original_dimensions'][0]}×{resize_result['original_dimensions'][1]}",
                "final_dimensions": f"{resize_result['final_dimensions'][0]}×{resize_result['final_dimensions'][1]}",
                "quality": resize_result['final_quality']
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading image: {str(e)}")


@app.get("/list")
async def list_all_albums():
    """
    List all albums with their images.
    
    Returns:
        Dictionary with album names and image lists
    """
    albums_folder = "albums"
    
    if not os.path.exists(albums_folder):
        return {"albums": {}}
    
    albums = {}
    
    try:
        for album_name in os.listdir(albums_folder):
            album_path = os.path.join(albums_folder, album_name)
            
            if not os.path.isdir(album_path):
                continue
            
            images = []
            for filename in os.listdir(album_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    images.append({
                        "filename": filename,
                        "url": f"/images/albums/{album_name}/{filename}"
                    })
            
            if images:
                albums[album_name] = {
                    "count": len(images),
                    "images": images
                }
        
        return {"albums": albums}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing albums: {str(e)}")


@app.get("/list/{album_name}")
async def list_album_images(album_name: str):
    """
    List all images in a specific album.
    
    Args:
        album_name: Name of the album folder
    
    Returns:
        List of images with metadata
    """
    # Validate album name
    if ".." in album_name or album_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid album name")
    
    album_path = os.path.join("albums", album_name)
    
    if not os.path.exists(album_path):
        raise HTTPException(status_code=404, detail=f"Album not found: {album_name}")
    
    images = []
    
    try:
        for filename in os.listdir(album_path):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(album_path, filename)
                file_size = os.path.getsize(file_path)
                images.append({
                    "filename": filename,
                    "size": file_size,
                    "size_formatted": resizer.format_size(file_size),
                    "url": f"/images/albums/{album_name}/{filename}"
                })
        
        return {
            "album": album_name,
            "count": len(images),
            "images": images
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing images: {str(e)}")


@app.post("/search")
async def search_faces(
    sample_image: UploadFile = File(...),
    album_folder: str = Form(...)
):
    """
    Search for faces matching a sample image in an album.
    Processes sample image in memory without saving to disk.
    
    Args:
        sample_image: Sample image file containing the face to search for
        album_folder: Album folder to search in
    
    Returns:
        Streaming response with matches
    """
    # Validate folder name
    if ".." in album_folder or album_folder.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid folder name")
    
    # Validate sample image file
    if not sample_image.filename:
        raise HTTPException(status_code=400, detail="No sample image provided")
    
    if not sample_image.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(status_code=400, detail="Sample image must be JPG, JPEG, or PNG")
    
    try:
        # Read sample image content into memory
        sample_content = await sample_image.read()
        
        # Load image from bytes using PIL
        sample_img = Image.open(io.BytesIO(sample_content))
        
        # Convert to RGB if necessary
        if sample_img.mode != 'RGB':
            sample_img = sample_img.convert('RGB')
        
        # Convert PIL image to numpy array for face_recognition
        sample_array = np.array(sample_img)
        
        # Extract face encoding from sample image
        face_encodings = face_recognition.face_encodings(sample_array)
        
        if len(face_encodings) == 0:
            raise HTTPException(status_code=400, detail="No face detected in sample image")
        
        # Use the first face found as reference
        searcher.reference_encoding = face_encodings[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing sample image: {str(e)}")
    
    # Verify album folder exists
    album_path = os.path.join("albums", album_folder)
    if not os.path.exists(album_path):
        raise HTTPException(status_code=404, detail=f"Album folder not found: {album_folder}")
    
    # Stream search results
    return StreamingResponse(
        searcher.stream_search(album_path),
        media_type="text/event-stream"
    )


@app.get("/images/albums/{album_name}/{image_name}")
async def get_image(album_name: str, image_name: str):
    """
    Serve static images from album folders.
    
    Args:
        album_name: Album folder name
        image_name: Image filename
    
    Returns:
        Image file
    """
    # Prevent directory traversal attacks
    if ".." in album_name or ".." in image_name:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    image_path = os.path.join("albums", album_name, image_name)
    
    # Verify the file exists
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")
    
    # Verify it's in the correct directory
    real_path = os.path.realpath(image_path)
    real_album = os.path.realpath(os.path.join("albums", album_name))
    
    if not real_path.startswith(real_album):
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # Verify it's an image file
    if not image_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    return FileResponse(image_path)


@app.delete("/albums/{album_name}")
async def delete_album(album_name: str):
    """
    Delete an entire album folder.
    
    Args:
        album_name: Album folder to delete
    
    Returns:
        Success message
    """
    if ".." in album_name or album_name.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid album name")
    
    album_path = os.path.join("albums", album_name)
    
    if not os.path.exists(album_path):
        raise HTTPException(status_code=404, detail=f"Album not found: {album_name}")
    
    try:
        shutil.rmtree(album_path)
        return {"status": "success", "message": f"Album '{album_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting album: {str(e)}")


@app.delete("/images/albums/{album_name}/{image_name}")
async def delete_image(album_name: str, image_name: str):
    """
    Delete a specific image from an album.
    
    Args:
        album_name: Album folder name
        image_name: Image filename to delete
    
    Returns:
        Success message
    """
    if ".." in album_name or ".." in image_name:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    image_path = os.path.join("albums", album_name, image_name)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Image not found")
    
    try:
        os.remove(image_path)
        return {"status": "success", "message": f"Image '{image_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting image: {str(e)}")


# Mount static files before catch-all route
app.mount("/static", StaticFiles(directory="static"), name="static")


# Serve index.html at root
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main HTML page."""
    index_path = "index.html"
    if not os.path.exists(index_path):
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)
    
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)