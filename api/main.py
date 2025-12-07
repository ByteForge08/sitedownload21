from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import json

app = FastAPI(title="Mr.Boombastic Downloader API")

# CORS para frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "service": "YouTube Info API"}

@app.get("/api/info")
async def get_video_info(url: str = Query(..., description="YouTube URL")):
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for fmt in info.get('formats', [])[:15]:  # Limitar para resposta menor
                if fmt.get('filesize') or fmt.get('filesize_approx'):
                    formats.append({
                        'id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': f"{fmt.get('height', '')}p" if fmt.get('height') else 'audio',
                        'size_mb': round((fmt.get('filesize') or fmt.get('filesize_approx', 0)) / (1024*1024), 2),
                        'note': fmt.get('format_note', ''),
                        'type': 'video+audio' if fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none' 
                                else 'audio' if fmt.get('acodec') != 'none' 
                                else 'video'
                    })
            
            return {
                'success': True,
                'title': info.get('title'),
                'author': info.get('uploader'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'view_count': info.get('view_count'),
                'formats': formats,
                'total_formats': len(formats)
            }
            
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": __import__('time').time()}

# Handler para Vercel (importante!)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)