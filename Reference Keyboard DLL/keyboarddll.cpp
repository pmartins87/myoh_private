//******************************************************************************
//
// This file is part of the OpenHoldem project
//    Source code:           https://github.com/OpenHoldem/openholdembot/
//    Forums:                http://www.maxinmontreal.com/forums/index.php
//    Licensed under GPL v3: http://www.gnu.org/licenses/gpl.html
//
//******************************************************************************
//
// Purpose: keyboarddll.cpp : Defines the entry point for the DLL application.
//
//******************************************************************************


//******************************************************************************
// keyboarddll.cpp : Humanized Keyboard Input with Dwell & Flight Dynamics
//******************************************************************************

#ifndef VC_EXTRALEAN
#define VC_EXTRALEAN
#endif

#ifndef WINVER
#define WINVER 0x0501
#endif

#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0501
#endif						

#ifndef _WIN32_WINDOWS
#define _WIN32_WINDOWS 0x0410
#endif

#ifndef _WIN32_IE
#define _WIN32_IE 0x0600
#endif

#include <windows.h>
#include <math.h>
#include <atlstr.h>
#include <random>
#include <chrono>
#include <thread>
#include <vector>
#include "keyboarddll.h"

// --- MOTOR DE ALEATORIEDADE (Mesmo padrão do mouse) ---
std::mt19937 rng_kbd(std::chrono::steady_clock::now().time_since_epoch().count());

// Helper: Gera um delay humano baseado em distribuição normal
// mean: média de tempo (ms)
// stddev: desvio padrão (variância)
void HumanDelay(double mean, double stddev) {
    std::normal_distribution<double> dist(mean, stddev);
    double val = dist(rng_kbd);
    if (val < 5.0) val = 5.0; // Mínimo físico
    std::this_thread::sleep_for(std::chrono::milliseconds((int)val));
}

// Helper: Envia um evento de tecla usando SendInput (API Moderna)
void SendInputKey(WORD vKey, bool keyUp) {
    INPUT input = { 0 };
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = vKey;
    input.ki.dwFlags = keyUp ? KEYEVENTF_KEYUP : 0;
    SendInput(1, &input, sizeof(INPUT));
}

// Funções de clique auxiliares (mantidas para compatibilidade interna do SendKey)
const double RandomNormal(const double m, const double s) {
    std::normal_distribution<double> distribution(m, s);
    return distribution(rng_kbd);
}

const double RandomNormalScaled(const double scale, const double m, const double s) {
    double res = -99;
    while (res < -3.5 || res > 3.5) res = RandomNormal(m, s);
    return (res / 3.5 * s + 1) * (scale / 2.0);
}

const void GetClickPoint(const int x, const int y, const int rx, const int ry, POINT *p) {
    p->x = x + (int)(RandomNormalScaled(2 * rx, 0, 1) + 0.5) - (rx);
    p->y = y + (int)(RandomNormalScaled(2 * ry, 0, 1) + 0.5) - (ry);
}

const POINT RandomizeClickLocation(const RECT rect) {
    POINT p = { 0 };
    GetClickPoint(rect.left + (rect.right - rect.left) / 2,
        rect.top + (rect.bottom - rect.top) / 2,
        (rect.right - rect.left) / 2,
        (rect.bottom - rect.top) / 2,
        &p);
    return p;
}

// --- FUNÇÃO DE ENVIO DE STRING HUMANIZADA ---
KEYBOARDDLL_API int SendString(const HWND hwnd, const RECT rect, const CString s, const bool use_comma)
{
    // Converte CString para standard string para facilitar
    CString strCopy = s;
    int len = strCopy.GetLength();

    for (int i = 0; i < len; i++)
    {
        char ch = strCopy[i];
        
        // Ajuste de ponto/vírgula conforme solicitado
        if (use_comma && ch == '.') ch = ',';

        // Obtém o Virtual Key e o estado do Shift/Ctrl/Alt
        short vkScan = VkKeyScan(ch);
        WORD vKey = LOBYTE(vkScan);
        WORD shiftState = HIBYTE(vkScan);

        bool needShift = (shiftState & 1) != 0;
        bool needCtrl  = (shiftState & 2) != 0;
        bool needAlt   = (shiftState & 4) != 0;

        // 1. Pressiona Modificadores (se necessário)
        if (needShift) SendInputKey(VK_SHIFT, false);
        if (needCtrl)  SendInputKey(VK_CONTROL, false);
        if (needAlt)   SendInputKey(VK_MENU, false);

        // Pequeno delay "físico" entre apertar shift e a tecla (10-30ms)
        if (needShift || needCtrl || needAlt) HumanDelay(20, 5);

        // 2. PRESSIONA A TECLA (KeyDown)
        SendInputKey(vKey, false);

        // --- DWELL TIME (O segredo da humanização) ---
        // Tempo que o dedo fica segurando a tecla.
        // Média: 75ms, Desvio: 20ms.
        HumanDelay(75, 20);

        // 3. SOLTA A TECLA (KeyUp)
        SendInputKey(vKey, true);

        // 4. Solta Modificadores (se necessário)
        if (needShift) SendInputKey(VK_SHIFT, true);
        if (needCtrl)  SendInputKey(VK_CONTROL, true);
        if (needAlt)   SendInputKey(VK_MENU, true);

        // --- FLIGHT TIME (Tempo de voo) ---
        // Tempo para mover o dedo até a próxima tecla.
        // Média: 110ms, Desvio: 30ms.
        // Se for a última tecla, não precisa esperar tanto.
        if (i < len - 1) {
            HumanDelay(110, 30);
        }
    }
    
    return (int)true;
}

// --- FUNÇÃO DE ENVIO DE TECLA ÚNICA (ATALHOS) ---
KEYBOARDDLL_API int SendKey(const HWND hwnd, const RECT rect, const char* vkey)
{
    // Lógica original de clicar para focar (Mantida mas suavizada os tempos)
    // NOTA: O clique aqui usa Teleporte (Absolute). Se possível, use o mousedll para focar antes.
    if (rect.left != -1 || rect.top != -1)
    {
        INPUT input[2] = { 0 };
        POINT pt = RandomizeClickLocation(rect);
        double fScreenWidth = ::GetSystemMetrics(SM_CXSCREEN) - 1;
        double fScreenHeight = ::GetSystemMetrics(SM_CYSCREEN) - 1;

        ClientToScreen(hwnd, &pt);
        double fx = pt.x * (65535.0f / fScreenWidth);
        double fy = pt.y * (65535.0f / fScreenHeight);

        // Clique Down
        input[0].type = INPUT_MOUSE;
        input[0].mi.dx = (LONG)fx;
        input[0].mi.dy = (LONG)fy;
        input[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN;
        SendInput(1, &input[0], sizeof(INPUT));

        // Delay humano do clique (segurar o botão do mouse)
        HumanDelay(60, 15);

        // Clique Up
        input[1].type = INPUT_MOUSE;
        input[1].mi.dx = (LONG)fx;
        input[1].mi.dy = (LONG)fy;
        input[1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP;
        SendInput(1, &input[1], sizeof(INPUT));
        
        // Delay para o Windows processar o foco antes de digitar
        HumanDelay(100, 20);
    }

    // Set focus to target window (Backup logic)
    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    // Identifica se é tecla composta (ex: Ctrl+C)
    // O OpenHoldem passa vkey[0] como modificador se vkey[1] existir? 
    // Analisando código antigo: Se for Ctrl/Shift/Alt no vkey[0], ele assume combo com vkey[1].
    
    bool isCombo = (vkey[0] == VK_CONTROL || vkey[0] == VK_SHIFT || vkey[0] == VK_MENU);

    if (isCombo) {
        // Pressiona Modificador
        SendInputKey(vkey[0], false);
        HumanDelay(30, 10);
        
        // Pressiona Tecla Principal
        SendInputKey(vkey[1], false);
        
        // Segura ambas (Dwell Time)
        HumanDelay(80, 20);
        
        // Solta Tecla Principal
        SendInputKey(vkey[1], true);
        HumanDelay(20, 10);
        
        // Solta Modificador
        SendInputKey(vkey[0], true);
    }
    else {
        // Tecla Simples
        SendInputKey(vkey[0], false);
        HumanDelay(75, 20); // Dwell Time
        SendInputKey(vkey[0], true);
    }

    return (int)true;
}

KEYBOARDDLL_API void ProcessMessage(const char *message, const void *param)
{
    if (message == NULL) return;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    return true;
}
