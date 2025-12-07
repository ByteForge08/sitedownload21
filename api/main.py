from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import time
import json

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "API Online", "service": "Mr.Boombastic"}

@app.get("/api/test")
def test():
    return {
        "status": "success",
        "message": "API funcionando",
        "timestamp": int(time.time())
    }

@app.get("/api/info")
async def get_info(url: str = Query(...)):
    """Obtém informações do vídeo do YouTube"""
    print(f"🔍 Processando URL: {url}")
    
    try:
        # Configurações otimizadas para Vercel
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Connection': 'keep-alive',
            }
        }
        
        print("📥 Iniciando extração com yt-dlp...")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair informações
            info = ydl.extract_info(url, download=False)
            print(f"✅ Informações extraídas: {info.get('title', 'Sem título')}")
            
            # Processar formatos
            formats = []
            for fmt in info.get('formats', []):
                # Calcular tamanho
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size_mb = round(filesize / (1024*1024), 2) if filesize else 0
                
                # Determinar tipo
                has_audio = fmt.get('acodec') != 'none'
                has_video = fmt.get('vcodec') != 'none'
                
                if has_audio and has_video:
                    format_type = 'video+audio'
                elif has_audio:
                    format_type = 'audio'
                else:
                    format_type = 'video'
                
                # Adicionar apenas formatos válidos
                if format_type in ['video+audio', 'audio'] or (format_type == 'video' and size_mb > 0):
                    formats.append({
                        'id': fmt.get('format_id', 'unknown'),
                        'ext': fmt.get('ext', 'unknown'),
                        'resolution': f"{fmt.get('height', '')}p" if fmt.get('height') else 'Audio',
                        'size_mb': size_mb,
                        'type': format_type,
                        'quality': fmt.get('format_note', 'Standard'),
                        'fps': fmt.get('fps'),
                        'codec': {
                            'video': fmt.get('vcodec'),
                            'audio': fmt.get('acodec')
                        }
                    })
            
            # Ordenar formatos
            formats.sort(key=lambda x: (
                0 if x['type'] == 'video+audio' else 
                1 if x['type'] == 'audio' else 2,
                -int(x['resolution'].replace('p', '')) if x['resolution'].replace('p', '').isdigit() else 0
            ))
            
            # Limitar número de formatos para resposta mais leve
            formats = formats[:15]
            
            return {
                'success': True,
                'title': info.get('title', 'Sem título'),
                'author': info.get('uploader', 'Desconhecido'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'formats': formats,
                'total_formats': len(formats),
                'best_video': next((f for f in formats if f['type'] == 'video+audio'), None),
                'best_audio': next((f for f in formats if f['type'] == 'audio'), None),
                'timestamp': int(time.time())
            }
            
    except yt_dlp.utils.DownloadError as e:
        print(f"❌ Erro yt-dlp: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Erro ao acessar vídeo: {str(e)[:100]}"
        )
    except Exception as e:
        print(f"💥 Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Erro interno: {str(e)[:100]}"
        )

@app.get("/api/simple")
async def simple_info(url: str = Query(...)):
    """Versão SIMPLES para teste"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            return {
                'success': True,
                'title': info.get('title', 'Teste'),
                'author': info.get('uploader', 'Teste'),
                'duration': info.get('duration', 120),
                'thumbnail': 'https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg',
                'formats': [
                    {'id': '18', 'resolution': '360p', 'type': 'video+audio', 'size_mb': 15.5},
                    {'id': '22', 'resolution': '720p', 'type': 'video+audio', 'size_mb': 45.2},
                    {'id': '140', 'resolution': 'Audio', 'type': 'audio', 'size_mb': 5.1}
                ],
                'test': 'modo_simples'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.get("/api/debug")
async def debug_info(url: str = Query(...)):
    """Endpoint de debug"""
    try:
        import yt_dlp.utils
        version = yt_dlp.utils.__version__
        
        return {
            'yt_dlp_version': version,
            'url_received': url,
            'status': 'debug',
            'timestamp': int(time.time())
        }
    except Exception as e:
        return {'error': str(e)}

@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": int(time.time())}
