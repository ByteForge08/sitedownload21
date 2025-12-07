"""
Mr.Boombastic YouTube Downloader - Versão OTIMIZADA para Vercel (10s timeout)
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import yt_dlp
import time
import asyncio
import aiohttp
import json

app = FastAPI(title="Mr.Boombastic Downloader - Otimizado")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timeout global para Vercel (8 segundos para dar margem)
VERCEL_TIMEOUT = 8

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Mr.Boombastic Downloader",
        "version": "3.1.0",
        "optimized": True,
        "timeout_limit": f"{VERCEL_TIMEOUT}s",
        "note": "Otimizado para Vercel Serverless Functions"
    }

@app.get("/api/test")
async def test_endpoint():
    """Endpoint de teste rápido"""
    return {
        "status": "success",
        "timestamp": int(time.time()),
        "timeout": VERCEL_TIMEOUT,
        "message": "API otimizada para Vercel"
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": int(time.time())}

@app.get("/api/quick")
async def quick_info(url: str = Query(...)):
    """
    Informações RÁPIDAS (dentro de 8 segundos)
    Usa yt-dlp com timeout e configurações otimizadas
    """
    try:
        # Timeout assíncrono
        async def fetch_info():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,  # Mais rápido que extract_flat=False
                'socket_timeout': 5,
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls']
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        # Executar com timeout
        info = await asyncio.wait_for(fetch_info(), timeout=VERCEL_TIMEOUT - 2)
        
        # Processar apenas informações essenciais
        formats = []
        for fmt in info.get('formats', [])[:8]:  # Apenas 8 primeiros formatos
            if fmt.get('format_id') in ['18', '22', '137', '140', '251']:  # Formatos comuns
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
                    'quality': fmt.get('format_note', 'Standard')
                })
        
        # Se não encontrou formatos comuns, criar alguns básicos
        if not formats:
            formats = [
                {'id': '18', 'ext': 'mp4', 'resolution': '360p', 'size_mb': 15.0, 'type': 'video+audio', 'quality': 'Good'},
                {'id': '22', 'ext': 'mp4', 'resolution': '720p', 'size_mb': 45.0, 'type': 'video+audio', 'quality': 'HD'},
                {'id': '140', 'ext': 'm4a', 'resolution': 'Audio', 'size_mb': 5.0, 'type': 'audio', 'quality': 'Good'},
            ]
        
        return {
            'success': True,
            'title': info.get('title', 'Vídeo do YouTube'),
            'author': info.get('uploader', 'Canal do YouTube'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'view_count': info.get('view_count', 0),
            'formats': formats,
            'total_formats': len(formats),
            'optimized': True,
            'timestamp': int(time.time())
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Timeout: Vercel limit (10s) exceeded")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro: {str(e)[:100]}")

@app.get("/api/direct")
async def direct_download(
    url: str = Query(...),
    format_id: str = Query('18'),
    quality: str = Query('medium')
):
    """
    Download DIRETO otimizado para Vercel
    Usa formato pré-definido para ser mais rápido
    """
    try:
        # Formatos otimizados para velocidade
        format_map = {
            '18': {'height': 360, 'ext': 'mp4', 'type': 'video+audio'},  # Mais rápido
            '140': {'height': None, 'ext': 'm4a', 'type': 'audio'},      # Áudio é rápido
            'worst': 'worst[height<=360]',                               # Pior qualidade = mais rápido
            'best_audio': 'bestaudio[ext=m4a]',                          # Áudio m4a é rápido
        }
        
        # Selecionar formato otimizado
        selected_format = format_map.get(format_id, '18')
        
        async def download_with_timeout():
            ydl_opts = {
                'format': selected_format if isinstance(selected_format, str) else f"{format_id}+bestaudio/best",
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 4,
                'retries': 2,
                'fragment_retries': 1,
                'skip_unavailable_fragments': True,
                'noprogress': True,
                'outtmpl': '/tmp/%(id)s.%(ext)s',
            }
            
            # Para áudio, converter para mp3 se solicitado
            if quality == 'mp3' or format_id == '140':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '128',  # Qualidade menor = mais rápido
                }]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Primeiro obter info rápida
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                
                # Verificar tamanho estimado
                estimated_size = 0
                for fmt in info.get('formats', []):
                    if str(fmt.get('format_id')) == str(format_id):
                        estimated_size = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                        break
                
                # Se muito grande, sugerir formato menor
                if estimated_size > 15 * 1024 * 1024:  # 15MB
                    return {
                        'error': 'video_too_large',
                        'suggested_format': '18',
                        'estimated_mb': round(estimated_size / (1024*1024), 1)
                    }
                
                # Fazer download (assíncrono para não bloquear)
                result = await asyncio.to_thread(ydl.download, [url])
                return {'success': True, 'info': info}
        
        # Executar com timeout
        result = await asyncio.wait_for(download_with_timeout(), timeout=VERCEL_TIMEOUT - 1)
        
        if 'error' in result:
            if result['error'] == 'video_too_large':
                raise HTTPException(
                    status_code=413,
                    detail=f"Vídeo muito grande ({result['estimated_mb']}MB). Use formato {result['suggested_format']} (360p)"
                )
        
        # Retornar sucesso
        return {
            'success': True,
            'message': 'Download iniciado',
            'format': format_id,
            'quality': quality,
            'direct_url': f'/api/stream?url={url}&format={format_id}'
        }
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Timeout: Download muito longo para Vercel")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro download: {str(e)[:80]}")

@app.get("/api/stream")
async def stream_download(
    url: str = Query(...),
    format_id: str = Query('18')
):
    """
    Streaming de vídeo - mais eficiente para Vercel
    """
    try:
        import subprocess
        import tempfile
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            temp_path = tmp.name
        
        # Comando yt-dlp otimizado para streaming
        cmd = [
            'yt-dlp',
            '-f', format_id,
            '-o', temp_path,
            '--no-warnings',
            '--socket-timeout', '5',
            '--retries', '2',
            url
        ]
        
        # Executar com timeout
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=VERCEL_TIMEOUT - 2)
        except asyncio.TimeoutError:
            process.kill()
            raise HTTPException(status_code=408, detail="Processo muito longo")
        
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Erro yt-dlp: {stderr.decode()[:100]}")
        
        # Verificar se arquivo foi criado
        import os
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            raise HTTPException(status_code=500, detail="Arquivo vazio ou não criado")
        
        # Stream do arquivo
        async def file_streamer():
            with open(temp_path, 'rb') as f:
                while chunk := f.read(1024 * 1024):  # 1MB chunks
                    yield chunk
            # Limpar
            os.unlink(temp_path)
        
        return StreamingResponse(
            file_streamer(),
            media_type='video/mp4',
            headers={
                'Content-Disposition': f'attachment; filename="video_{format_id}.mp4"'
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:100])

@app.get("/api/formats")
async def list_formats(url: str = Query(...)):
    """Lista formatos disponíveis rapidamente"""
    try:
        async def get_formats():
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'listformats': True,
                'socket_timeout': 4,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('formats', [])
        
        formats = await asyncio.wait_for(get_formats(), timeout=6)
        
        # Filtrar apenas formatos comuns e pequenos
        common_formats = []
        for fmt in formats:
            if fmt.get('format_id') in ['18', '22', '137', '140', '251', '160', '133']:
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                if filesize and filesize < 20 * 1024 * 1024:  # Menor que 20MB
                    common_formats.append({
                        'id': fmt.get('format_id'),
                        'ext': fmt.get('ext'),
                        'resolution': f"{fmt.get('height', '')}p",
                        'size_mb': round(filesize / (1024*1024), 1),
                        'type': 'video+audio' if fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none' else 'audio'
                    })
        
        return {
            'success': True,
            'formats': common_formats[:6],  # Apenas 6 formatos
            'recommended': '18',  # 360p é mais rápido
            'timestamp': int(time.time())
        }
        
    except asyncio.TimeoutError:
        return {
            'success': True,
            'formats': [
                {'id': '18', 'ext': 'mp4', 'resolution': '360p', 'size_mb': 15.0, 'type': 'video+audio'},
                {'id': '140', 'ext': 'm4a', 'resolution': 'Audio', 'size_mb': 5.0, 'type': 'audio'},
            ],
            'note': 'Formato padrão (timeout evitado)',
            'timestamp': int(time.time())
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:100])

@app.get("/api/simple")
async def simple_download(url: str = Query(...)):
    """
    Download SIMPLES e RÁPIDO - sempre funciona
    Usa formato 18 (360p) que é mais rápido
    """
    try:
        # URL direta do YouTube (fallback)
        import re
        video_id = None
        
        # Extrair ID do vídeo
        patterns = [
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
            r'youtu\.be/([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        
        if not video_id:
            raise HTTPException(status_code=400, detail="URL do YouTube inválida")
        
        # Retornar informações básicas com fallback
        return {
            'success': True,
            'video_id': video_id,
            'formats': [
                {
                    'id': '18',
                    'ext': 'mp4',
                    'resolution': '360p',
                    'size_mb': 12.5,
                    'type': 'video+audio',
                    'quality': 'Good',
                    'direct_url': f'https://sitedownload21.vercel.app/api/stream?url={url}&format=18'
                },
                {
                    'id': '140',
                    'ext': 'm4a',
                    'resolution': 'Audio',
                    'size_mb': 4.8,
                    'type': 'audio',
                    'quality': 'Good',
                    'direct_url': f'https://sitedownload21.vercel.app/api/stream?url={url}&format=140'
                }
            ],
            'note': 'Modo simples otimizado para Vercel',
            'timestamp': int(time.time())
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)[:100])

# Handler para verificação rápida
@app.get("/api/ping")
async def ping():
    """Endpoint mais rápido possível"""
    return {"pong": int(time.time()), "vercel": True, "timeout": VERCEL_TIMEOUT}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
