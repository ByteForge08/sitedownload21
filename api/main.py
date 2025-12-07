"""
Mr.Boombastic YouTube Downloader - API Completa
Com sistema de download real (com limitações da Vercel)
"""
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import yt_dlp
import time
import json
import os
import tempfile
import uuid
import asyncio
from typing import Optional
import aiofiles
import mimetypes

app = FastAPI(
    title="Mr.Boombastic Downloader API",
    description="API para download de vídeos do YouTube",
    version="3.0.0"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Banco de dados em memória (em produção use Redis/DB)
downloads_db = {}
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50MB limite

# ==================== ENDPOINTS DE INFORMAÇÃO ====================

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "Mr.Boombastic Downloader",
        "version": "3.0.0",
        "endpoints": {
            "info": "/api/info?url=URL",
            "formats": "/api/formats?url=URL",
            "download": "/api/download?url=URL&format=ID",
            "direct": "/api/direct?url=URL&format=ID",
            "health": "/api/health",
            "test": "/api/test"
        },
        "limits": {
            "max_duration": "10s (Vercel)",
            "max_size": "50MB",
            "supported_formats": "mp4, webm, m4a, mp3"
        }
    }

@app.get("/api/test")
async def test_endpoint():
    """Endpoint de teste básico"""
    return {
        "status": "success",
        "message": "API Mr.Boombastic funcionando!",
        "timestamp": int(time.time()),
        "features": ["info", "formats", "download", "direct"]
    }

@app.get("/api/health")
async def health_check():
    """Health check para monitoramento"""
    return {
        "status": "healthy",
        "service": "youtube-downloader",
        "timestamp": int(time.time()),
        "downloads_pending": len([d for d in downloads_db.values() if d.get("status") == "pending"]),
        "downloads_completed": len([d for d in downloads_db.values() if d.get("status") == "completed"])
    }

@app.get("/api/info")
async def get_video_info(
    url: str = Query(..., description="URL do YouTube"),
    detailed: bool = Query(False, description="Informações detalhadas")
):
    """Obtém informações completas do vídeo"""
    try:
        print(f"🔍 Obtendo informações para: {url}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                raise HTTPException(status_code=404, detail="Vídeo não encontrado")
            
            # Processar formatos disponíveis
            formats = []
            audio_formats = []
            video_formats = []
            combined_formats = []
            
            for fmt in info.get('formats', []):
                # Ignorar formatos sem ID
                if not fmt.get('format_id'):
                    continue
                
                # Calcular tamanho
                filesize = fmt.get('filesize') or fmt.get('filesize_approx')
                size_mb = round(filesize / (1024 * 1024), 2) if filesize else 0
                
                # Determinar tipo
                has_audio = fmt.get('acodec') != 'none'
                has_video = fmt.get('vcodec') != 'none'
                
                if has_audio and has_video:
                    format_type = 'video+audio'
                    combined_formats.append(fmt)
                elif has_audio:
                    format_type = 'audio'
                    audio_formats.append(fmt)
                else:
                    format_type = 'video'
                    video_formats.append(fmt)
                
                # Adicionar à lista geral
                format_data = {
                    'id': fmt.get('format_id'),
                    'ext': fmt.get('ext'),
                    'resolution': f"{fmt.get('height', '')}p" if fmt.get('height') else 'Audio',
                    'size_mb': size_mb,
                    'type': format_type,
                    'quality': fmt.get('format_note', 'Standard'),
                    'fps': fmt.get('fps'),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec'),
                    'bitrate': fmt.get('abr') or fmt.get('tbr'),
                    'filesize': filesize
                }
                formats.append(format_data)
            
            # Encontrar melhores formatos
            def get_best_format(formats_list, prefer_ext=None):
                if not formats_list:
                    return None
                
                # Ordenar por qualidade/tamanho
                sorted_formats = sorted(
                    formats_list,
                    key=lambda x: (
                        x.get('height') or 0,
                        x.get('width') or 0,
                        x.get('filesize') or 0
                    ),
                    reverse=True
                )
                
                if prefer_ext:
                    for fmt in sorted_formats:
                        if fmt.get('ext') == prefer_ext:
                            return fmt
                
                return sorted_formats[0] if sorted_formats else None
            
            best_video = get_best_format(combined_formats, 'mp4')
            best_audio = get_best_format(audio_formats, 'm4a')
            
            # Construir resposta
            response = {
                'success': True,
                'url': url,
                'title': info.get('title', 'Sem título'),
                'author': info.get('uploader', 'Desconhecido'),
                'channel_url': info.get('uploader_url', ''),
                'duration': info.get('duration', 0),
                'duration_formatted': _format_duration(info.get('duration', 0)),
                'thumbnail': info.get('thumbnail', ''),
                'view_count': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                'categories': info.get('categories', []),
                'upload_date': info.get('upload_date', ''),
                'formats_count': len(formats),
                'timestamp': int(time.time())
            }
            
            if detailed:
                response['formats'] = formats
                response['best_video'] = _format_to_response(best_video) if best_video else None
                response['best_audio'] = _format_to_response(best_audio) if best_audio else None
            else:
                # Apenas formatos principais
                main_formats = []
                for fmt in formats:
                    if fmt['type'] == 'video+audio' and fmt['ext'] in ['mp4', 'webm']:
                        main_formats.append(fmt)
                    elif fmt['type'] == 'audio' and fmt['ext'] in ['m4a', 'mp3', 'webm']:
                        main_formats.append(fmt)
                
                response['formats'] = main_formats[:10]  # Limitar a 10 formatos
            
            return response
            
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail=f"Erro YouTube: {str(e)}")
    except Exception as e:
        print(f"💥 Erro interno: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/api/formats")
async def get_formats_only(url: str = Query(...)):
    """Apenas formatos disponíveis (resposta mais leve)"""
    try:
        info = await get_video_info(url, detailed=True)
        return {
            'success': True,
            'formats': info.get('formats', []),
            'best_video': info.get('best_video'),
            'best_audio': info.get('best_audio'),
            'total': len(info.get('formats', []))
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ==================== SISTEMA DE DOWNLOAD ====================

@app.get("/api/download")
async def start_download(
    url: str = Query(..., description="URL do YouTube"),
    format_id: str = Query(None, description="ID do formato (ex: '18', '140')"),
    quality: str = Query('best', description="Qualidade: 'best', 'worst', 'audio', 'video'"),
    filename: str = Query(None, description="Nome personalizado do arquivo")
):
    """
    Inicia download de vídeo/áudio
    Retorna URL para download ou streaming
    """
    try:
        print(f"📥 Iniciando download: {url} | formato: {format_id or quality}")
        
        # Gerar ID único para este download
        download_id = str(uuid.uuid4())[:8]
        
        # Configurar opções baseadas no formato
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': f'/tmp/%(title)s.%(ext)s',
            'progress_hooks': [lambda d: _download_progress_hook(d, download_id)],
        }
        
        # Definir formato
        if format_id:
            ydl_opts['format'] = format_id
        elif quality == 'best':
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
        elif quality == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
        elif quality == 'video':
            ydl_opts['format'] = 'bestvideo/best'
        elif quality == 'worst':
            ydl_opts['format'] = 'worst'
        
        # Para MP3
        if quality == 'audio' and not format_id:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            ydl_opts['outtmpl'] = f'/tmp/%(title)s.%(ext)s'
        
        # Registrar download
        downloads_db[download_id] = {
            "status": "processing",
            "url": url,
            "format": format_id or quality,
            "progress": 0,
            "filename": None,
            "filesize": None,
            "start_time": time.time(),
            "error": None
        }
        
        # Executar download em background
        import threading
        thread = threading.Thread(
            target=_download_task,
            args=(url, ydl_opts, download_id, filename),
            daemon=True
        )
        thread.start()
        
        return {
            "success": True,
            "download_id": download_id,
            "status": "started",
            "message": "Download iniciado em segundo plano",
            "check_status": f"/api/download/{download_id}/status",
            "download_url": f"/api/download/{download_id}/file",
            "estimated_time": "10-30 segundos"
        }
        
    except Exception as e:
        print(f"❌ Erro ao iniciar download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.get("/api/download/{download_id}/status")
async def get_download_status(download_id: str):
    """Verifica status do download"""
    if download_id not in downloads_db:
        raise HTTPException(status_code=404, detail="Download não encontrado")
    
    download_info = downloads_db[download_id]
    
    # Calcular tempo decorrido
    elapsed = time.time() - download_info.get("start_time", time.time())
    
    response = {
        "download_id": download_id,
        "status": download_info.get("status", "unknown"),
        "progress": download_info.get("progress", 0),
        "elapsed_seconds": round(elapsed, 2),
        "filename": download_info.get("filename"),
        "filesize_mb": download_info.get("filesize"),
        "error": download_info.get("error")
    }
    
    # Se concluído, adicionar URL de download
    if download_info.get("status") == "completed" and download_info.get("filename"):
        response["download_url"] = f"/api/download/{download_id}/file"
        response["direct_url"] = f"/api/direct?path={download_info['filename']}"
    
    return response

@app.get("/api/download/{download_id}/file")
async def download_file(download_id: str):
    """Faz download do arquivo"""
    if download_id not in downloads_db:
        raise HTTPException(status_code=404, detail="Download não encontrado")
    
    download_info = downloads_db[download_id]
    
    if download_info.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Download ainda não concluído")
    
    filename = download_info.get("filename")
    if not filename or not os.path.exists(filename):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    
    # Determinar tipo MIME
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    # Verificar tamanho do arquivo
    filesize = os.path.getsize(filename)
    if filesize > MAX_DOWNLOAD_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"Arquivo muito grande ({filesize/(1024*1024):.1f}MB). Limite: {MAX_DOWNLOAD_SIZE/(1024*1024)}MB"
        )
    
    # Retornar arquivo
    return FileResponse(
        filename,
        media_type=mime_type,
        filename=os.path.basename(filename),
        headers={
            "Content-Disposition": f"attachment; filename={os.path.basename(filename)}",
            "X-Download-ID": download_id,
            "X-File-Size": str(filesize)
        }
    )

@app.get("/api/direct")
async def direct_download(
    url: str = Query(..., description="URL do YouTube"),
    format_id: str = Query('18', description="ID do formato (padrão: 18=360p)"),
    stream: bool = Query(False, description="Stream em vez de download")
):
    """
    Download direto (apenas para vídeos curtos < 10MB)
    Ideal para áudios ou vídeos curtos
    """
    try:
        print(f"⚡ Download direto: {url} | formato: {format_id}")
        
        # Criar diretório temporário
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, 'download_%(id)s.%(ext)s')
        
        # Configurações para download rápido
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'keepvideo': False,
        }
        
        # Para áudio, converter para MP3
        if format_id in ['140', '251'] or 'audio' in format_id:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        # Executar download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Primeiro obter informações
            info = ydl.extract_info(url, download=False)
            
            # Verificar tamanho estimado
            estimated_size = 0
            for fmt in info.get('formats', []):
                if fmt.get('format_id') == format_id:
                    estimated_size = fmt.get('filesize') or fmt.get('filesize_approx') or 0
                    break
            
            if estimated_size > 20 * 1024 * 1024:  # 20MB
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "Vídeo muito grande para download direto",
                        "estimated_size_mb": round(estimated_size / (1024*1024), 1),
                        "suggestion": "Use /api/download para downloads maiores"
                    }
                )
            
            # Fazer download
            result = ydl.download([url])
            
            # Encontrar arquivo baixado
            downloaded_files = os.listdir(temp_dir)
            if not downloaded_files:
                raise HTTPException(status_code=500, detail="Nenhum arquivo foi baixado")
            
            downloaded_file = os.path.join(temp_dir, downloaded_files[0])
            
            # Verificar tamanho real
            actual_size = os.path.getsize(downloaded_file)
            if actual_size > MAX_DOWNLOAD_SIZE:
                os.remove(downloaded_file)
                raise HTTPException(
                    status_code=413,
                    detail=f"Arquivo muito grande ({actual_size/(1024*1024):.1f}MB)"
                )
            
            # Determinar tipo MIME
            mime_type, _ = mimetypes.guess_type(downloaded_file)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Nome do arquivo
            safe_title = "".join(c for c in info.get('title', 'video') if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_title:
                safe_title = 'video'
            
            ext = downloaded_file.split('.')[-1] if '.' in downloaded_file else 'mp4'
            output_filename = f"{safe_title[:50]}.{ext}"
            
            # Limpar outros arquivos temporários
            for file in os.listdir(temp_dir):
                if file != os.path.basename(downloaded_file):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except:
                        pass
            
            if stream:
                # Streaming response
                async def file_streamer():
                    async with aiofiles.open(downloaded_file, 'rb') as f:
                        while chunk := await f.read(1024 * 1024):  # 1MB chunks
                            yield chunk
                    # Limpar após streaming
                    try:
                        os.remove(downloaded_file)
                        os.rmdir(temp_dir)
                    except:
                        pass
                
                return StreamingResponse(
                    file_streamer(),
                    media_type=mime_type,
                    headers={
                        "Content-Disposition": f"attachment; filename={output_filename}",
                        "X-Direct-Download": "true",
                        "X-Video-Title": info.get('title', 'video')
                    }
                )
            else:
                # File response
                return FileResponse(
                    downloaded_file,
                    media_type=mime_type,
                    filename=output_filename,
                    headers={
                        "Content-Disposition": f"attachment; filename={output_filename}",
                        "X-Direct-Download": "true",
                        "X-Video-Title": info.get('title', 'video')
                    }
                )
            
    except Exception as e:
        print(f"❌ Erro download direto: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro download: {str(e)}")

# ==================== FUNÇÕES AUXILIARES ====================

def _format_duration(seconds: int) -> str:
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

def _format_to_response(fmt):
    """Converte formato yt-dlp para resposta da API"""
    if not fmt:
        return None
    
    filesize = fmt.get('filesize') or fmt.get('filesize_approx')
    
    return {
        'id': fmt.get('format_id'),
        'ext': fmt.get('ext'),
        'resolution': f"{fmt.get('height', '')}p" if fmt.get('height') else 'Audio',
        'size_mb': round(filesize / (1024 * 1024), 2) if filesize else 0,
        'vcodec': fmt.get('vcodec'),
        'acodec': fmt.get('acodec'),
        'bitrate': fmt.get('abr') or fmt.get('tbr'),
        'fps': fmt.get('fps')
    }

def _download_progress_hook(d, download_id):
    """Callback de progresso do download"""
    if download_id not in downloads_db:
        return
    
    if d['status'] == 'downloading':
        if 'total_bytes' in d and d['total_bytes']:
            percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
            downloads_db[download_id]['progress'] = round(percent, 2)
            downloads_db[download_id]['filesize'] = round(d['total_bytes'] / (1024 * 1024), 2)
    elif d['status'] == 'finished':
        downloads_db[download_id]['status'] = 'completed'
        downloads_db[download_id]['progress'] = 100
        downloads_db[download_id]['filename'] = d['filename']
        print(f"✅ Download concluído: {download_id} -> {d['filename']}")
    elif d['status'] == 'error':
        downloads_db[download_id]['status'] = 'error'
        downloads_db[download_id]['error'] = str(d.get('error', 'Erro desconhecido'))

def _download_task(url, ydl_opts, download_id, custom_filename=None):
    """Tarefa de download em background"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extrair informações primeiro
            info = ydl.extract_info(url, download=False)
            
            # Atualizar nome do arquivo se especificado
            if custom_filename:
                ext = ydl_opts.get('merge_output_format', 'mp4')
                if 'postprocessors' in ydl_opts:
                    for pp in ydl_opts['postprocessors']:
                        if pp.get('key') == 'FFmpegExtractAudio':
                            ext = pp.get('preferredcodec', 'mp3')
                
                # Criar caminho com nome personalizado
                temp_dir = '/tmp'
                new_filename = os.path.join(temp_dir, f"{custom_filename}.{ext}")
                ydl_opts['outtmpl'] = new_filename
                
                print(f"📝 Usando nome personalizado: {new_filename}")
            
            # Executar download
            ydl.download([url])
            
            # Atualizar status se não foi atualizado pelo hook
            if downloads_db[download_id]['status'] == 'processing':
                downloads_db[download_id]['status'] = 'completed'
                downloads_db[download_id]['progress'] = 100
                
    except Exception as e:
        print(f"❌ Erro na tarefa de download {download_id}: {str(e)}")
        downloads_db[download_id]['status'] = 'error'
        downloads_db[download_id]['error'] = str(e)
        
        # Limpar arquivos temporários em caso de erro
        try:
            if 'outtmpl' in ydl_opts:
                import glob
                for file in glob.glob(ydl_opts['outtmpl'].replace('%(title)s', '*')):
                    try:
                        os.remove(file)
                    except:
                        pass
        except:
            pass

@app.get("/api/cleanup")
async def cleanup_old_downloads():
    """Limpa downloads antigos (manutenção)"""
    try:
        current_time = time.time()
        to_delete = []
        
        for download_id, info in downloads_db.items():
            start_time = info.get('start_time', 0)
            if current_time - start_time > 3600:  # 1 hora
                to_delete.append(download_id)
                
                # Tentar remover arquivo
                filename = info.get('filename')
                if filename and os.path.exists(filename):
                    try:
                        os.remove(filename)
                    except:
                        pass
        
        # Remover do banco de dados
        for download_id in to_delete:
            del downloads_db[download_id]
        
        return {
            "success": True,
            "cleaned": len(to_delete),
            "remaining": len(downloads_db),
            "message": f"Removidos {len(to_delete)} downloads antigos"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CONFIGURAÇÃO DE TIPOS MIME ====================
mimetypes.add_type('audio/mp4', '.m4a')
mimetypes.add_type('audio/webm', '.webm')
mimetypes.add_type('video/webm', '.webm')
mimetypes.add_type('application/x-mpegURL', '.m3u8')

# ==================== INICIALIZAÇÃO ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
