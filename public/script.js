let fastMode = true;

function enableFastMode() {
    fastMode = !fastMode;
    const btn = document.getElementById('fastModeBtn');
    if (fastMode) {
        btn.innerHTML = '<i class="fas fa-bolt"></i> Modo Rápido (ON)';
        btn.style.background = 'rgba(46, 204, 113, 0.2)';
        btn.style.borderColor = '#2ecc71';
        showMessage('✅ Modo Rápido: Usando formatos otimizados para Vercel', 'success');
    } else {
        btn.innerHTML = '<i class="fas fa-bolt"></i> Modo Rápido (OFF)';
        btn.style.background = '';
        btn.style.borderColor = '';
        showMessage('ℹ️ Modo Normal: Pode ser mais lento na Vercel', 'info');
    }
}
