@echo off
:: Garante que o script rode na pasta correta
cd /d "C:\Users\Caixa\Desktop\personal\myoh_git"

echo ==========================================
echo    ATUALIZADOR AUTOMATICO DE GITHUB
echo ==========================================
echo.

:: Mostra o status atual (o que mudou)
git status -s
echo.

:: Pergunta a descrição. Se der Enter sem nada, usa uma padrão.
set /p msg="Digite a descricao da alteracao (ou Enter para 'Update Rapido'): "
if "%msg%"=="" set msg=Update Rapido

echo.
echo Adicionando arquivos...
git add .

echo.
echo Registrando (Commit)...
git commit -m "%msg%"

echo.
echo Enviando para nuvem (Push)...
git push

echo.
echo ==========================================
echo           PROCESSO CONCLUIDO
echo ==========================================
pause