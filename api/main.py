"""
Mr.Boombastic YouTube Downloader API
Versão Final para Vercel
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import time
import json

app = FastAPI(
    title="Mr.Boombastic Downloader API",
    description="API para obter informações de vídeos do YouTube",
    version="2.0.0"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache simples em memória (para não sobrecarregar a API)
info_cache = {}
CACHE_TIMEOUT = 300  # 5 minutos

@app.get("/")
async def root():
    """Página inicial da API"""
    return {
        "status": "online",
        "service": "Mr.Boombastic YouTube Downloader",
        "version": "2.0.0",
        "endpoints": {
            "info": "/api/info?url=YOUTUBE_URL",
            "test": "/api/test",
            "health": "/api/health"
        },
        "timestamp": int(time.time())
    }

@app.get("/api/info")
async def get_video_info(
    url: str = Query(..., description="URL completa do vídeo do YouTube"),
    refresh: bool = Query(False, description="Forçar atualização do cache")
):
    """
    Obtém informações detalhadas do vídeo do YouTube
    Retorna: título, autor, duração, thumbnail e formatos disponíveis
    """
    try:
        # Verificar cache (se não for refresh)
        cache_key = f"info_{hash(url)}"
        if not refresh and cache_key in info_cache:
            cached_time, cached_data = info_cache[cache_key]
            if time.time() - cached_time < CACHE_TIMEOUT:
                cached_data["cached"] = True
                return cached_data
        
        # Configurações do yt-dlp
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair informações
            info = ydl.extract_info(url, download=False)
            
            # Processar formatos disponíveis
            formats = []
            for fmt in info.get('formats', []):
                # Calcular tamanho aproximado
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size_mb = round(filesize / (1024 * 1024), 2) if filesize else 0
                
                # Determinar tipo
                has_audio = fmt.get('acodec') != 'none'
                has_video = fmt.get('vcodec') != 'none'
                
                if has_audio and has_video:
                    format_type = 'video+audio'
                elif has_audio:
                    format_type = 'audio'
                else:
                    format_type = 'video'
                
                # Adicionar formato à lista
                format_data = {
                    'id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': f"{fmt.get('height', '')}p" if fmt.get('height') else 'Audio',
                    'fps': fmt.get('fps'),
                    'filesize_mb': size_mb,
                    'type': format_type,
                    'quality': fmt.get('format_note', ''),
                    'codecs': {
                        'video': fmt.get('vcodec'),
                        'audio': fmt.get('acodec')
                    }
                }
                
                # Filtrar formatos muito pequenos (geralmente incompletos)
                if size_mb > 0.1 or format_type == 'audio':
                    formats.append(format_data)
            
            # Ordenar formatos: primeiro video+audio, depois por resolução
            formats.sort(key=lambda x: (
                0 if x['type'] == 'video+audio' else 
                1 if x['type'] == 'video' else 2,
                -int(x['resolution'].replace('p', '')) if x['resolution'].isdigit() else 0
            ))
            
            # Construir resposta
            result = {
                'success': True,
                'url': url,
                'title': info.get('title', 'Sem título'),
                'author': info.get('uploader', 'Desconhecido'),
                'channel_url': info.get('uploader_url', ''),
                'duration_seconds': info.get('duration', 0),
                'duration_formatted': format_duration(info.get('duration', 0)),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'description': info.get('description', '')[:500] + '...' if info.get('description') else '',
                'categories': info.get('categories', []),
                'tags': info.get('tags', [])[:10],
                'upload_date': info.get('upload_date', ''),
                'formats': formats[:20],  # Limitar a 20 formatos
                'total_formats': len(formats),
                'best_video': next((f for f in formats if f['type'] == 'video+audio'), None),
                'best_audio': next((f for f in formats if f['type'] == 'audio'), None),
                'timestamp': int(time.time()),
                'cached': False
            }
            
            # Salvar no cache
            info_cache[cache_key] = (time.time(), result)
            
            return result
            
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Erro ao acessar vídeo: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)}"
        )

@app.get("/api/test")
async def test_endpoint():
    """Endpoint de teste da API"""
    return {
        "status": "success",
        "message": "API Mr.Boombastic está funcionando!",
        "endpoint": "/api/info?url=https://www.youtube.com/watch?v=...",
        "example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "timestamp": int(time.time())
    }

@app.get("/api/health")
async def health_check():
    """Health check para monitoramento"""
    return {
        "status": "healthy",
        "service": "mrboombastic-api",
        "timestamp": int(time.time()),
        "cache_size": len(info_cache)
    }

@app.get("/api/formats/{url:path}")
async def get_formats_only(url: str):
    """Endpoint específico para apenas formatos (resposta mais leve)"""
    try:
        result = await get_video_info(url)
        return {
            "success": True,
            "formats": result.get("formats", []),
            "total": result.get("total_formats", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

def format_duration(seconds: int) -> str:
    """Formata duração em segundos para HH:MM:SS"""
    if not seconds:
        return "00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

# Handler para execução local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
