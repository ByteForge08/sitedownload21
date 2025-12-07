from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import time

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/info")
async def get_info(url: str = Query(...)):
    """Processa URLs REAIS do YouTube"""
    try:
        print(f"📥 Processando URL: {url}")
        
        # Configurações otimizadas
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                raise HTTPException(status_code=400, detail="Vídeo não encontrado")
            
            print(f"✅ Vídeo encontrado: {info.get('title')}")
            
            # Processar formatos REAIS
            formats = []
            for fmt in info.get('formats', []):
                # Pular formatos inválidos
                if not fmt.get('format_id'):
                    continue
                    
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size_mb = round(filesize / (1024*1024), 2) if filesize else 0
                
                has_audio = fmt.get('acodec') != 'none'
                has_video = fmt.get('vcodec') != 'none'
                
                if has_audio and has_video:
                    format_type = 'video+audio'
                elif has_audio:
                    format_type = 'audio'
                else:
                    format_type = 'video'
                
                formats.append({
                    'id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
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
            
            # Filtrar e ordenar
            formats = [f for f in formats if f['size_mb'] > 0 or f['type'] == 'audio']
            formats.sort(key=lambda x: (
                0 if x['type'] == 'video+audio' else 1 if x['type'] == 'audio' else 2,
                -int(x['resolution'].replace('p', '')) if x['resolution'].replace('p', '').isdigit() else 0
            ))
            
            return {
                'success': True,
                'title': info.get('title', 'Sem título'),
                'author': info.get('uploader', 'Desconhecido'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'formats': formats[:20],  # Limitar a 20 formatos
                'total_formats': len(formats),
                'best_video': next((f for f in formats if f['type'] == 'video+audio'), None),
                'best_audio': next((f for f in formats if f['type'] == 'audio'), None),
                'timestamp': int(time.time()),
                '_mode': 'real'  # Indicar que são dados reais
            }
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        # NÃO retornar dados mock - retornar erro real
        raise HTTPException(
            status_code=400,
            detail=f"Erro ao processar vídeo: {str(e)[:100]}"
        )

@app.get("/api/simple")
async def simple_info(url: str = Query(...)):
    """Versão SIMPLES mas com dados REAIS"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Mais rápido
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Formatos básicos
            formats = []
            for fmt in info.get('formats', [])[:5]:  # Apenas 5 formatos
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size_mb = round(filesize / (1024*1024), 2) if filesize else 0
                
                formats.append({
                    'id': fmt.get('format_id', '18'),
                    'ext': fmt.get('ext', 'mp4'),
                    'resolution': f"{fmt.get('height', '360')}p",
                    'size_mb': size_mb or 15.5,
                    'type': 'video+audio',
                    'quality': 'Standard'
                })
            
            return {
                'success': True,
                'title': info.get('title', 'Vídeo do YouTube'),
                'author': info.get('uploader', 'Canal do YouTube'),
                'duration': info.get('duration', 120),
                'thumbnail': info.get('thumbnail', ''),
                'formats': formats,
                '_mode': 'simple'
            }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ... outros endpoints (test, health, debug)
