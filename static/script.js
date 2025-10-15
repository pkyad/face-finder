let eventSource = null;
let searchMatches = [];
let searchReader = null;

function switchTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });

    document.getElementById(tabName).classList.add('active');
    event.target.classList.add('active');

    if (tabName === 'albums') {
        loadAlbums();
    }
}

function getServerUrl() {
    return '';  // Empty string means use same server
}

function showStatus(elementId, message, type = 'info') {
    const element = document.getElementById(elementId);
    element.innerHTML = message;
    element.className = `status-message show ${type}`;
}

function updateFileName() {
    const file = document.getElementById('imageFile').files[0];
    if (file) {
        document.getElementById('fileName').textContent = `✓ ${file.name}`;
        document.getElementById('fileName').style.display = 'block';
    }
}

function updateSampleFileName() {
    const file = document.getElementById('sampleImageFile').files[0];
    const fileNameDiv = document.getElementById('sampleFileName');
    const previewDiv = document.getElementById('samplePreview');
    const previewImg = document.getElementById('samplePreviewImg');
    
    if (file) {
        fileNameDiv.textContent = `✓ ${file.name}`;
        fileNameDiv.style.display = 'block';
        
        // Show preview
        const reader = new FileReader();
        reader.onload = function(e) {
            previewImg.src = e.target.result;
            previewDiv.style.display = 'block';
        };
        reader.readAsDataURL(file);
    } else {
        fileNameDiv.style.display = 'none';
        previewDiv.style.display = 'none';
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('fileLabel').classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('imageFile').files = files;
        updateFileName();
    }
}

function handleSampleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.classList.remove('dragover');
}

function handleSampleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('sampleFileLabel').classList.remove('dragover');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('sampleImageFile').files = files;
        updateSampleFileName();
    }
}

async function uploadImage() {
    const serverUrl = getServerUrl();
    const albumName = document.getElementById('albumNameUpload').value.trim();
    const imageFile = document.getElementById('imageFile').files[0];

    if (!albumName) {
        showStatus('uploadStatus', '❌ Please enter album name', 'error');
        return;
    }

    if (!imageFile) {
        showStatus('uploadStatus', '❌ Please select an image', 'error');
        return;
    }

    showStatus('uploadStatus', '<span class="spinner"></span>Uploading and resizing...', 'loading');

    const formData = new FormData();
    formData.append('folder_name', albumName);
    formData.append('image', imageFile);

    try {
        const response = await fetch(`${serverUrl}/upload`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();
            showStatus('uploadStatus', '✅ Image uploaded and resized successfully', 'success');
            
            const details = result.resizing;
            const html = `
                <table class="table">
                    <tr>
                        <td><strong>File:</strong></td>
                        <td>${result.filename}</td>
                    </tr>
                    <tr>
                        <td><strong>Album:</strong></td>
                        <td>${result.folder}</td>
                    </tr>
                    <tr>
                        <td><strong>Original Size:</strong></td>
                        <td>${details.original_size}</td>
                    </tr>
                    <tr>
                        <td><strong>Final Size:</strong></td>
                        <td>${details.final_size}</td>
                    </tr>
                    <tr>
                        <td><strong>Compression:</strong></td>
                        <td>${details.compression}</td>
                    </tr>
                    <tr>
                        <td><strong>Original Dimensions:</strong></td>
                        <td>${details.original_dimensions}</td>
                    </tr>
                    <tr>
                        <td><strong>Final Dimensions:</strong></td>
                        <td>${details.final_dimensions}</td>
                    </tr>
                    <tr>
                        <td><strong>Quality:</strong></td>
                        <td>${details.quality}</td>
                    </tr>
                </table>
            `;
            document.getElementById('uploadDetails').innerHTML = html;
            document.getElementById('uploadPreview').style.display = 'block';
            
            clearUploadForm();
        } else {
            const error = await response.json();
            showStatus('uploadStatus', `❌ Error: ${error.detail}`, 'error');
        }
    } catch (error) {
        showStatus('uploadStatus', `❌ Upload failed: ${error.message}`, 'error');
    }
}

function clearUploadForm() {
    document.getElementById('imageFile').value = '';
    document.getElementById('fileName').style.display = 'none';
}

function clearSearchForm() {
    document.getElementById('sampleImageFile').value = '';
    document.getElementById('sampleFileName').style.display = 'none';
    document.getElementById('samplePreview').style.display = 'none';
    document.getElementById('searchAlbum').value = '';
    document.getElementById('resultsGallery').innerHTML = '';
    document.getElementById('searchSummary').classList.remove('show');
    document.getElementById('searchStatus').innerHTML = '';
}

async function startSearch() {
    const serverUrl = getServerUrl();
    const sampleImageFile = document.getElementById('sampleImageFile').files[0];
    const searchAlbum = document.getElementById('searchAlbum').value.trim();

    if (!sampleImageFile) {
        showStatus('searchStatus', '❌ Please upload a sample image with the face to search', 'error');
        return;
    }

    if (!searchAlbum) {
        showStatus('searchStatus', '❌ Please enter album to search', 'error');
        return;
    }

    searchMatches = [];
    document.getElementById('resultsGallery').innerHTML = '';
    document.getElementById('searchSummary').classList.remove('show');

    showStatus('searchStatus', '<span class="spinner"></span>Starting face recognition search...', 'loading');
    document.getElementById('startSearchBtn').disabled = true;
    document.getElementById('stopSearchBtn').disabled = false;

    const formData = new FormData();
    formData.append('sample_image', sampleImageFile);
    formData.append('album_folder', searchAlbum);

    try {
        const response = await fetch(`${serverUrl}/search`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            searchReader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await searchReader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const message = line.substring(6);
                        handleSearchMessage(message, serverUrl, searchAlbum);
                    }
                }
            }
        } else {
            const error = await response.json();
            showStatus('searchStatus', `❌ Error: ${error.detail}`, 'error');
        }
    } catch (error) {
        if (error.name !== 'AbortError') {
            showStatus('searchStatus', `❌ Search failed: ${error.message}`, 'error');
        }
    } finally {
        document.getElementById('startSearchBtn').disabled = false;
        document.getElementById('stopSearchBtn').disabled = true;
        searchReader = null;
    }
}

function handleSearchMessage(message, serverUrl, searchAlbum) {
    if (message.startsWith('error:')) {
        showStatus('searchStatus', `❌ ${message}`, 'error');
    } else if (message.startsWith('✅ MATCH')) {
        const regex = /✅ MATCH (\d+): (.+?) \| Confidence: ([\d.]+)%/;
        const match = message.match(regex);
        if (match) {
            const matchNum = parseInt(match[1]);
            const filename = match[2];
            const confidence = parseFloat(match[3]).toFixed(1);

            searchMatches.push({ matchNum, filename, confidence });
            addSearchResultCard(filename, confidence, matchNum, serverUrl, searchAlbum);
            showStatus('searchStatus', `🎉 Found ${matchNum} match${matchNum !== 1 ? 'es' : ''}...`, 'success');
        }
    } else if (message.startsWith('🎯 Search Complete')) {
        showStatus('searchStatus', `✅ Search complete! Found ${searchMatches.length} matches.`, 'success');
        showSearchSummary();
    } else if (message.startsWith('Searching')) {
        showStatus('searchStatus', `<span class="spinner"></span>${message}`, 'loading');
    }
}

function addSearchResultCard(filename, confidence, matchNum, serverUrl, albumName) {
    const gallery = document.getElementById('resultsGallery');
    const imageUrl = `${serverUrl}/images/albums/${albumName}/${filename}`;
    
    const card = document.createElement('div');
    card.className = 'image-card';
    card.innerHTML = `
        <img src="${imageUrl}" alt="${filename}" onclick="showImageModal('${imageUrl}', '${filename}', '${confidence}', '${albumName}')">
        <div class="image-info">
            <div class="image-name">${filename}</div>
            <div class="image-meta">Album: ${albumName}</div>
            <div class="image-meta">Match #${matchNum}</div>
            <div class="confidence">Confidence: ${confidence}%</div>
        </div>
    `;
    gallery.appendChild(card);
}

function showSearchSummary() {
    const summary = document.getElementById('searchSummary');
    if (searchMatches.length === 0) {
        summary.innerHTML = `
            <h3>No Matches Found</h3>
            <p>No faces matched the reference image with sufficient confidence.</p>
        `;
    } else {
        const avgConfidence = (searchMatches.reduce((sum, m) => sum + parseFloat(m.confidence), 0) / searchMatches.length).toFixed(1);
        const maxConfidence = Math.max(...searchMatches.map(m => parseFloat(m.confidence))).toFixed(1);
        const minConfidence = Math.min(...searchMatches.map(m => parseFloat(m.confidence))).toFixed(1);
        
        summary.innerHTML = `
            <h3>🎉 Search Results Summary</h3>
            <p><strong>Total Matches:</strong> ${searchMatches.length}</p>
            <p><strong>Average Confidence:</strong> ${avgConfidence}%</p>
            <p><strong>Highest Confidence:</strong> ${maxConfidence}%</p>
            <p><strong>Lowest Confidence:</strong> ${minConfidence}%</p>
        `;
    }
    summary.classList.add('show');
}

function stopSearch() {
    if (searchReader) {
        searchReader.cancel();
        searchReader = null;
        showStatus('searchStatus', '⚠️ Search stopped by user', 'info');
        document.getElementById('startSearchBtn').disabled = false;
        document.getElementById('stopSearchBtn').disabled = true;
    }
}

async function loadAlbums() {
    const serverUrl = getServerUrl();
    showStatus('albumsStatus', '<span class="spinner"></span>Loading albums...', 'loading');

    try {
        const response = await fetch(`${serverUrl}/list`);
        if (response.ok) {
            const data = await response.json();
            displayAlbums(data.albums);
            showStatus('albumsStatus', `✅ Loaded ${Object.keys(data.albums).length} album(s)`, 'success');
        } else {
            showStatus('albumsStatus', '❌ Failed to load albums', 'error');
        }
    } catch (error) {
        showStatus('albumsStatus', `❌ Error: ${error.message}`, 'error');
    }
}

function displayAlbums(albums) {
    const container = document.getElementById('albumsContainer');
    const imagesContainer = document.getElementById('imagesContainer');
    
    if (Object.keys(albums).length === 0) {
        container.innerHTML = '<div class="empty-state">No albums found. Upload images to create albums!</div>';
        imagesContainer.innerHTML = '<div class="empty-state">No images to display</div>';
        return;
    }

    let albumsHtml = '';
    let allImagesHtml = '<div class="gallery">';
    
    for (const [albumName, albumData] of Object.entries(albums)) {
        const serverUrl = getServerUrl();
        
        albumsHtml += `
            <div class="album-card">
                <div class="album-name">📁 ${albumName}</div>
                <div class="album-count">${albumData.count} image${albumData.count !== 1 ? 's' : ''}</div>
                <div class="album-images">
                    ${albumData.images.slice(0, 6).map(img => `
                        <img src="${serverUrl}${img.url}" 
                                class="album-thumb" 
                                alt="${img.filename}"
                                onclick="showImageModal('${serverUrl}${img.url}', '${img.filename}', null, '${albumName}')"
                                title="${img.filename}">
                    `).join('')}
                    ${albumData.count > 6 ? `<div style="padding: 20px; color: #666;">+${albumData.count - 6} more</div>` : ''}
                </div>
                <div class="button-group">
                    <button class="btn-secondary btn-small" onclick="viewAlbumDetails('${albumName}')">View All</button>
                    <button class="btn-danger btn-small" onclick="deleteAlbum('${albumName}')">Delete Album</button>
                </div>
            </div>
        `;

        albumData.images.forEach(img => {
            allImagesHtml += `
                <div class="image-card">
                    <img src="${serverUrl}${img.url}" alt="${img.filename}" 
                            onclick="showImageModal('${serverUrl}${img.url}', '${img.filename}', null, '${albumName}')">
                    <div class="image-info">
                        <div class="image-name">${img.filename}</div>
                        <div class="image-meta">Album: ${albumName}</div>
                        <div class="action-buttons">
                            <button class="btn-danger btn-small" onclick="deleteImage('${albumName}', '${img.filename}')">Delete</button>
                        </div>
                    </div>
                </div>
            `;
        });
    }
    
    allImagesHtml += '</div>';
    container.innerHTML = albumsHtml;
    imagesContainer.innerHTML = allImagesHtml;
}

async function viewAlbumDetails(albumName) {
    const serverUrl = getServerUrl();
    
    try {
        const response = await fetch(`${serverUrl}/list/${albumName}`);
        if (response.ok) {
            const data = await response.json();
            
            let html = `
                <h2>📁 Album: ${albumName}</h2>
                <p style="color: #666; margin-bottom: 20px;">${data.count} image${data.count !== 1 ? 's' : ''}</p>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Filename</th>
                            <th>Size</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.images.map(img => `
                            <tr>
                                <td>${img.filename}</td>
                                <td>${img.size_formatted}</td>
                                <td>
                                    <div class="action-buttons">
                                        <button class="btn-secondary btn-small" 
                                                onclick="showImageModal('${serverUrl}${img.url}', '${img.filename}', null, '${albumName}')">
                                            View
                                        </button>
                                        <button class="btn-danger btn-small" 
                                                onclick="deleteImage('${albumName}', '${img.filename}'); closeModal();">
                                            Delete
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            
            document.getElementById('modalContent').innerHTML = html;
            document.getElementById('imageModal').style.display = 'block';
        }
    } catch (error) {
        showStatus('albumsStatus', `❌ Error loading album: ${error.message}`, 'error');
    }
}

async function deleteAlbum(albumName) {
    if (!confirm(`Are you sure you want to delete the album "${albumName}" and all its images?`)) {
        return;
    }

    const serverUrl = getServerUrl();
    showStatus('albumsStatus', '<span class="spinner"></span>Deleting album...', 'loading');

    try {
        const response = await fetch(`${serverUrl}/albums/${albumName}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showStatus('albumsStatus', `✅ Album "${albumName}" deleted successfully`, 'success');
            loadAlbums();
        } else {
            const error = await response.json();
            showStatus('albumsStatus', `❌ Error: ${error.detail}`, 'error');
        }
    } catch (error) {
        showStatus('albumsStatus', `❌ Delete failed: ${error.message}`, 'error');
    }
}

async function deleteImage(albumName, imageName) {
    if (!confirm(`Delete "${imageName}"?`)) {
        return;
    }

    const serverUrl = getServerUrl();
    showStatus('albumsStatus', '<span class="spinner"></span>Deleting image...', 'loading');

    try {
        const response = await fetch(`${serverUrl}/images/albums/${albumName}/${imageName}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showStatus('albumsStatus', `✅ Image deleted successfully`, 'success');
            loadAlbums();
        } else {
            const error = await response.json();
            showStatus('albumsStatus', `❌ Error: ${error.detail}`, 'error');
        }
    } catch (error) {
        showStatus('albumsStatus', `❌ Delete failed: ${error.message}`, 'error');
    }
}

async function getServerStatus() {
    const serverUrl = getServerUrl();
    showStatus('statusContainer', '<span class="spinner"></span>Loading server status...', 'loading');

    try {
        const response = await fetch(`${serverUrl}/status`);
        if (response.ok) {
            const data = await response.json();
            displayServerStatus(data);
        } else {
            document.getElementById('statusContainer').innerHTML = 
                '<div class="status-message show error">❌ Failed to load server status</div>';
        }
    } catch (error) {
        document.getElementById('statusContainer').innerHTML = 
            `<div class="status-message show error">❌ Error: ${error.message}</div>`;
    }
}

function displayServerStatus(data) {
    const container = document.getElementById('statusContainer');
    
    const html = `
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">${data.status === 'running' ? '✅' : '❌'}</div>
                <div class="stat-label">Server Status</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${data.reference_loaded ? '✅' : '❌'}</div>
                <div class="stat-label">Reference Loaded</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${(data.face_recognition.tolerance * 100).toFixed(0)}%</div>
                <div class="stat-label">Face Tolerance</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">${data.face_recognition.min_confidence}%</div>
                <div class="stat-label">Min Confidence</div>
            </div>
        </div>

        <div style="margin-top: 30px;">
            <h3 style="margin-bottom: 15px;">📋 Configuration Details</h3>
            <table class="table">
                <tr>
                    <td><strong>Server Status:</strong></td>
                    <td>${data.status}</td>
                </tr>
                <tr>
                    <td><strong>Reference Face Loaded:</strong></td>
                    <td>${data.reference_loaded ? 'Yes' : 'No'}</td>
                </tr>
                <tr>
                    <td><strong>Reference Path:</strong></td>
                    <td>${data.reference_path || 'None'}</td>
                </tr>
                <tr>
                    <td><strong>Face Recognition Tolerance:</strong></td>
                    <td>${data.face_recognition.tolerance}</td>
                </tr>
                <tr>
                    <td><strong>Minimum Confidence:</strong></td>
                    <td>${data.face_recognition.min_confidence}%</td>
                </tr>
                <tr>
                    <td><strong>Target Image Size:</strong></td>
                    <td>${data.image_resizing.target_size_kb}KB</td>
                </tr>
                <tr>
                    <td><strong>Max Image Dimension:</strong></td>
                    <td>${data.image_resizing.max_dimension}px</td>
                </tr>
                <tr>
                    <td><strong>JPEG Quality:</strong></td>
                    <td>${data.image_resizing.jpeg_quality}</td>
                </tr>
            </table>
        </div>

        <div style="margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
            <h3 style="margin-bottom: 15px;">ℹ️ About This Server</h3>
            <p style="color: #666; line-height: 1.6;">
                This is a FastAPI-based face recognition server that automatically resizes uploaded images 
                to optimize them for face recognition processing. Images are compressed to approximately 500KB 
                with a maximum dimension of 1920px while maintaining quality and aspect ratio.
            </p>
            <p style="color: #666; line-height: 1.6; margin-top: 10px;">
                The face recognition system uses a tolerance-based matching algorithm with real-time 
                streaming results. Matches are returned as soon as they are found during the search process.
            </p>
        </div>
    `;
    
    container.innerHTML = html;
}

function showImageModal(imageUrl, filename, confidence, albumName) {
    let html = `
        <img src="${imageUrl}" alt="${filename}">
        <h3>${filename}</h3>
        <p style="color: #666; margin-bottom: 15px;">Album: ${albumName}</p>
    `;
    
    if (confidence) {
        html += `<div class="confidence" style="display: inline-block;">Confidence: ${confidence}%</div>`;
    }
    
    html += `
        <div style="margin-top: 20px;">
            <button class="btn-danger" onclick="deleteImage('${albumName}', '${filename}'); closeModal();">Delete Image</button>
            <button class="btn-secondary" onclick="closeModal()">Close</button>
        </div>
    `;
    
    document.getElementById('modalContent').innerHTML = html;
    document.getElementById('imageModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('imageModal').style.display = 'none';
}

window.onclick = function(event) {
    const modal = document.getElementById('imageModal');
    if (event.target == modal) {
        closeModal();
    }
}