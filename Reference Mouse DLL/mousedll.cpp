//******************************************************************************
//
// This file is part of the OpenHoldem project
//    Source code:           https://github.com/OpenHoldem/openholdembot/
//    Forums:                http://www.maxinmontreal.com/forums/index.php
//    Licensed under GPL v3: http://www.gnu.org/licenses/gpl.html
//
//******************************************************************************
//
// Purpose: mousedll.cpp : Defines the entry point for the DLL application.
//
//******************************************************************************


//******************************************************************************
// mousedll.cpp : Humanized Mouse Movement with Bezier Curves & Overshoot
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
#include "mousedll.h"
#include <chrono>
#include <thread> // Necessário para sleep_for
#include <random> // Necessário para geração humana de números
#include <cmath>  // Necessário para seno/cosseno

// --- VARIÁVEIS GLOBAIS (NÃO APAGUE) ---
// Global variables for speed and smoothness factor
double speedFactor = 1.0;
int fluidityFactor = 20;

// Motor de aleatoriedade moderno (Iniciado uma vez)
std::mt19937 rng_mouse(std::chrono::steady_clock::now().time_since_epoch().count());

// --- FUNÇÕES DE CONFIGURAÇÃO (NÃO APAGUE) ---

// Function to adjust the speed factor
MOUSEDLL_API void SetMouseSpeed(double factor) {
    speedFactor = factor;
}

// Function to adjust the smoothness factor
MOUSEDLL_API void SetMouseFluidity(int factor) {
    fluidityFactor = factor;
}

// --- LÓGICA DE MOVIMENTO HUMANIZADA ---

void MoveMouseHuman(POINT start, POINT end, int duration_ms) {
    // 1. Aplica o Fator de Velocidade do Usuário
    // Se speedFactor for 0.66, o tempo será 66% do original (Mais rápido)
    duration_ms = static_cast<int>(duration_ms * speedFactor);
    
    // Proteção para não ficar instantâneo (robótico)
    // Para multitabling, 30ms é um bom limite inferior (muito rápido, mas físico)
    if (duration_ms < 30) duration_ms = 30;

    // Variação humana natural no tempo (+- 10%)
    std::uniform_int_distribution<int> time_noise(-duration_ms/10, duration_ms/10);
    duration_ms += time_noise(rng_mouse);

    // Calcula a distância total
    double distTotal = sqrt(pow(end.x - start.x, 2) + pow(end.y - start.y, 2));

    // Define passos baseado na fluidez e tempo. 
    // Para multitabling, garantimos eficiência.
    int steps = (duration_ms / 1000.0) * (fluidityFactor * 15); 
    if (steps < 6) steps = 6; // Mínimo de passos para ter uma curva

    // --- PONTO DE CONTROLE DA BÉZIER (O ARCO) ---
    std::uniform_int_distribution<int> arc_dist(-30, 30);
    POINT control;
    // Arco menor para quem joga rápido (movimento mais econômico)
    double arcScale = distTotal * 0.15; 
    control.x = (start.x + end.x) / 2 + (int)((arc_dist(rng_mouse) / 100.0) * arcScale);
    control.y = (start.y + end.y) / 2 + (int)((arc_dist(rng_mouse) / 100.0) * arcScale);

    // --- OVERSHOOT (PASSAR DO PONTO) ---
    // Em multitabling, overshoot grande atrapalha. Vamos fazer um micro-overshoot.
    bool doOvershoot = (distTotal > 300); // Só em distâncias grandes
    double overshootX = 0, overshootY = 0;
    
    if (doOvershoot) {
        std::uniform_real_distribution<double> over_dist(0.0, 1.0);
        // Apenas 15% de chance de overshoot para não perder tempo
        if (over_dist(rng_mouse) > 0.85) { 
             overshootX = (end.x - start.x) * 0.02; // 2% da distância
             overshootY = (end.y - start.y) * 0.02;
        }
    }

    auto startTime = std::chrono::high_resolution_clock::now();
    POINT lastPos;
    GetCursorPos(&lastPos);

    // Jitter (Tremor)
    std::uniform_real_distribution<double> freq_dist(2.0, 5.0);
    double freq = freq_dist(rng_mouse); 

    for (int i = 0; i <= steps; i++) {
        POINT currentPos;
        GetCursorPos(&currentPos);

        // Segurança: Se o mouse mexeu >15px fora do esperado, aborta (Humano assumiu)
        if (abs(currentPos.x - lastPos.x) > 15 || abs(currentPos.y - lastPos.y) > 15) {
            return; 
        }

        double t = (double)i / steps;
        
        // Easing: SineInOut modificado para ser responsivo
        double easeT = 0.5 * (1 - cos(t * 3.14159));

        // Curva Bézier
        double u = 1 - easeT;
        double tt = easeT * easeT;
        double uu = u * u;

        double bx = (uu * start.x) + (2 * u * easeT * control.x) + (tt * end.x);
        double by = (uu * start.y) + (2 * u * easeT * control.y) + (tt * end.y);

        // Jitter Suave (reduzido para não atrapalhar a velocidade)
        double noiseAmplitude = (sin(t * 3.14159) * 2.0); 
        double noiseX = sin(t * freq * 2 * 3.14) * noiseAmplitude;
        double noiseY = cos(t * freq * 2 * 3.14) * noiseAmplitude;

        // Overshoot
        double currentOvershootX = 0;
        double currentOvershootY = 0;
        if (doOvershoot) {
             double overT = sin(t * 3.14159); 
             currentOvershootX = overshootX * overT;
             currentOvershootY = overshootY * overT;
        }

        int finalX = (int)(bx + noiseX + currentOvershootX);
        int finalY = (int)(by + noiseY + currentOvershootY);

        SetCursorPos(finalX, finalY);
        lastPos.x = finalX;
        lastPos.y = finalY;

        // Controle de Tempo Preciso
        auto now = std::chrono::high_resolution_clock::now();
        double targetElapsed = duration_ms * t;
        double actualElapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - startTime).count();
        
        if (targetElapsed > actualElapsed) {
             int wait = (int)(targetElapsed - actualElapsed);
             if(wait > 0) std::this_thread::sleep_for(std::chrono::milliseconds(wait));
        }
    }
    
    // Garante posição final exata
    SetCursorPos(end.x, end.y);
    
    // Pausa pós-movimento (reduzida para multitabling)
    // Se o mouse for muito rápido (0.66), a pausa é menor (10-30ms)
    int reaction_min = (int)(20 * speedFactor);
    int reaction_max = (int)(50 * speedFactor);
    if (reaction_min < 5) reaction_min = 5;
    
    std::uniform_int_distribution<int> reaction_dist(reaction_min, reaction_max);
    std::this_thread::sleep_for(std::chrono::milliseconds(reaction_dist(rng_mouse)));
}

// --- FUNÇÕES DE CLIQUE E ARRASTE (MANTIDAS) ---

// Auxiliares para o clique
const double RandomNormal(const double m, const double s) {
    std::normal_distribution<double> distribution(m, s);
    return distribution(rng_mouse);
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
    POINT p = {0};
    GetClickPoint(rect.left + (rect.right - rect.left) / 2, 
                  rect.top + (rect.bottom - rect.top) / 2, 
                  (rect.right - rect.left) / 2, 
                  (rect.bottom - rect.top) / 2, 
                  &p);
    return p;
}

MOUSEDLL_API int MouseClick(const HWND hwnd, const RECT rect, const MouseButton button, const int clicks)
{
    INPUT input[100] = {0};
    POINT pt = RandomizeClickLocation(rect);
    double fScreenWidth = ::GetSystemMetrics(SM_CXSCREEN) - 1;
    double fScreenHeight = ::GetSystemMetrics(SM_CYSCREEN) - 1;

    ClientToScreen(hwnd, &pt);
    double fx = pt.x * (65535.0f / fScreenWidth);
    double fy = pt.y * (65535.0f / fScreenHeight);

    POINT currentPos;
    GetCursorPos(&currentPos);

    // Move o mouse usando a função humanizada
    // Tempo base aleatório entre 150 e 250ms (antes do speedFactor)
    std::uniform_int_distribution<int> move_time(150, 250);
    MoveMouseHuman(currentPos, pt, move_time(rng_mouse));

    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    for (int i = 0; i < clicks; i++)
    {
        ZeroMemory(&input[i*2], sizeof(INPUT));
        input[i*2].type = INPUT_MOUSE;
        input[i*2].mi.dx = (LONG)fx;
        input[i*2].mi.dy = (LONG)fy;

        switch (button)
        {
        case MouseLeft:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN; break;
        case MouseMiddle:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_MIDDLEDOWN; break;
        case MouseRight:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTDOWN; break;
        }
        
        SendInput(1, &input[i*2], sizeof(INPUT));
        
        // Delay aleatório entre apertar e soltar (clique humano)
        std::uniform_int_distribution<int> click_hold(20, 70);
        std::this_thread::sleep_for(std::chrono::milliseconds(click_hold(rng_mouse)));

        ZeroMemory(&input[i*2+1], sizeof(INPUT));
        input[i*2+1].type = INPUT_MOUSE;
        input[i*2+1].mi.dx = (LONG)fx;
        input[i*2+1].mi.dy = (LONG)fy;
        
        switch (button)
        {
        case MouseLeft:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP; break;
        case MouseMiddle:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_MIDDLEUP; break;
        case MouseRight:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTUP; break;
        }

        SendInput(1, &input[i*2+1], sizeof(INPUT));

        if (i < clicks - 1) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50 + rand() % 100));
        }
    }

    return (int)true;
}

MOUSEDLL_API int MouseClickDrag(const HWND hwnd, const RECT rect) {
    // Implementação segura de Drag para Sliders
    INPUT input[3];
    POINT start, end;
    double fx, fy;
    double fScreenWidth = ::GetSystemMetrics(SM_CXSCREEN) - 1;
    double fScreenHeight = ::GetSystemMetrics(SM_CYSCREEN) - 1;

    // Começa onde o mouse já está (assumindo que já movemos para o handle)
    GetCursorPos(&start);
    
    // Termina em um ponto proporcional (75% da largura da região)
    // Isso evita arrastar até a borda extrema
    end.x = rect.left + (long)((rect.right - rect.left) * 0.75); 
    end.y = start.y; // Mantém linha reta horizontal

    // Move até o inicio (curto ajuste)
    MoveMouseHuman(start, start, 50);

    fx = start.x * (65535.0f / fScreenWidth);
    fy = start.y * (65535.0f / fScreenHeight);

    ZeroMemory(&input[0], sizeof(INPUT));
    input[0].type = INPUT_MOUSE;
    input[0].mi.dx = (LONG)fx;
    input[0].mi.dy = (LONG)fy;
    input[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN;
    
    // Executa o clique segura (Down)
    SendInput(1, &input[0], sizeof(INPUT));

    // Arrasta suavemente
    MoveMouseHuman(start, end, 300);

    fx = end.x * (65535.0f / fScreenWidth);
    fy = end.y * (65535.0f / fScreenHeight);

    ZeroMemory(&input[1], sizeof(INPUT));
    input[1].type = INPUT_MOUSE;
    input[1].mi.dx = (LONG)fx;
    input[1].mi.dy = (LONG)fy;
    input[1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE;
    
    // Executa o movimento final
    SendInput(1, &input[1], sizeof(INPUT));

    ZeroMemory(&input[2], sizeof(INPUT));
    input[2].type = INPUT_MOUSE;
    input[2].mi.dwFlags = MOUSEEVENTF_LEFTUP;
    
    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    // Solta
    SendInput(1, &input[2], sizeof(INPUT));
    return (int)true;
}

// Stub para compatibilidade
MOUSEDLL_API void ProcessMessage(const char *message, const void *param) {
    if (message == NULL) return;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    return true;
}