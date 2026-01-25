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

// Global variables for speed and smoothness factor
double speedFactor = 1.0;
int fluidityFactor = 20;

// Function to adjust the speed factor
MOUSEDLL_API void SetMouseSpeed(double factor) {
    speedFactor = factor;
}

// Function to adjust the smoothness factor
MOUSEDLL_API void SetMouseFluidity(int factor) {
    fluidityFactor = factor;
}

// Easing function for more natural movement
double EaseInOutQuad(double t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

void MoveMouseHuman(POINT start, POINT end, int duration_ms) {
    int steps = fluidityFactor;
    duration_ms = static_cast<int>(duration_ms * speedFactor);
    auto startTime = std::chrono::high_resolution_clock::now();
    POINT lastPos;
    GetCursorPos(&lastPos);
    
    // Calculate a control point for the Bézier curve
    POINT control;
    control.x = (start.x + end.x) / 2 + (rand() % 100 - 50);
    control.y = (start.y + end.y) / 2 + (rand() % 100 - 50);
    
    for (int i = 0; i <= steps; i++) {
        POINT currentPos;
        GetCursorPos(&currentPos);
        
        // Check if the user has moved the mouse
        if (currentPos.x != lastPos.x || currentPos.y != lastPos.y) {
            // The user has moved the mouse, we are waiting for him to stop
            do {
                Sleep(50);
                lastPos = currentPos;
                GetCursorPos(&currentPos);
            } while (currentPos.x != lastPos.x || currentPos.y != lastPos.y);
            
            // Wait an extra second
            Sleep(1000);
            
            // Reset movement from new position
            start = currentPos;
            control.x = (start.x + end.x) / 2 + (rand() % 100 - 50);
            control.y = (start.y + end.y) / 2 + (rand() % 100 - 50);
            i = 0;
            startTime = std::chrono::high_resolution_clock::now();
            continue;
        }
        
        double t = (double)i / steps;
        
        // Use a quadratic Bézier curve for movement
        double x = (1-t)*(1-t)*start.x + 2*(1-t)*t*control.x + t*t*end.x;
        double y = (1-t)*(1-t)*start.y + 2*(1-t)*t*control.y + t*t*end.y;
        
        // Add a small random deviation
        x += (rand() % 3) - 1;
        y += (rand() % 3) - 1;

        SetCursorPos((int)x, (int)y);
        lastPos.x = (int)x;
        lastPos.y = (int)y;
        
        // Calculate elapsed time and adjust delay
        auto now = std::chrono::high_resolution_clock::now();
        auto elapsedTime = std::chrono::duration_cast<std::chrono::milliseconds>(now - startTime).count();
        int remainingTime = (duration_ms / steps) - elapsedTime;
        if (remainingTime > 0) {
            Sleep(remainingTime);
        }
        startTime = std::chrono::high_resolution_clock::now();
    }
}

MOUSEDLL_API int MouseClick(const HWND hwnd, const RECT rect, const MouseButton button, const int clicks)
{
    INPUT input[100] = {0};

    POINT pt = RandomizeClickLocation(rect);
    double fScreenWidth = ::GetSystemMetrics(SM_CXSCREEN) - 1;
    double fScreenHeight = ::GetSystemMetrics(SM_CYSCREEN) - 1;

    // Translate click point to screen/mouse coords
    ClientToScreen(hwnd, &pt);
    double fx = pt.x * (65535.0f / fScreenWidth);
    double fy = pt.y * (65535.0f / fScreenHeight);

    // Get current mouse position
    POINT currentPos;
    GetCursorPos(&currentPos);

    // Move mouse to target position
    MoveMouseHuman(currentPos, pt, 200 + rand() % 100); // Durée entre 200 et 299 ms

    // Set focus to target window
    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);

    // Set up the input structure
    for (int i = 0; i < clicks; i++)
    {
        ZeroMemory(&input[i*2], sizeof(INPUT));
        input[i*2].type = INPUT_MOUSE;
        input[i*2].mi.dx = (LONG)fx;
        input[i*2].mi.dy = (LONG)fy;

        switch (button)
        {
        case MouseLeft:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN;
            break;
        case MouseMiddle:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_MIDDLEDOWN;
            break;
        case MouseRight:
            input[i*2].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTDOWN;
            break;
        }
        
        // Send the mouse down event
        SendInput(1, &input[i*2], sizeof(INPUT));

        // Introduce a random delay between press and release (20 to 80 ms)
        Sleep(20 + rand() % 61);

        ZeroMemory(&input[i*2+1], sizeof(INPUT));
        input[i*2+1].type = INPUT_MOUSE;
        input[i*2+1].mi.dx = (LONG)fx;
        input[i*2+1].mi.dy = (LONG)fy;

        switch (button)
        {
        case MouseLeft:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTUP;
            break;
        case MouseMiddle:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_MIDDLEUP;
            break;
        case MouseRight:
            input[i*2+1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_RIGHTUP;
            break;
        }

        // Send the mouse up event
        SendInput(1, &input[i*2+1], sizeof(INPUT));

        // If there are more clicks, add a delay between them (50 to 150 ms)
        if (i < clicks - 1) {
            Sleep(50 + rand() % 101);
        }
    }

    return (int)true;
}

MOUSEDLL_API int MouseClickDrag(const HWND hwnd, const RECT rect) {
    INPUT input[3];
    POINT start, end;
    double fx, fy;

    double fScreenWidth = ::GetSystemMetrics(SM_CXSCREEN) - 1;
    double fScreenHeight = ::GetSystemMetrics(SM_CYSCREEN) - 1;

    // Set up start and end points
    start.x = rect.left;
    start.y = rect.top + (rect.bottom - rect.top) / 2;
    end.x = rect.right;
    end.y = rect.top + (rect.bottom - rect.top) / 2;

    ClientToScreen(hwnd, &start);
    ClientToScreen(hwnd, &end);

    // Move mouse to start position
    MoveMouseHuman(start, start, 200 + rand() % 100);

    fx = start.x * (65535.0f / fScreenWidth);
    fy = start.y * (65535.0f / fScreenHeight);

    ZeroMemory(&input[0], sizeof(INPUT));
    input[0].type = INPUT_MOUSE;
    input[0].mi.dx = (LONG)fx;
    input[0].mi.dy = (LONG)fy;
    input[0].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE | MOUSEEVENTF_LEFTDOWN;

    // Move mouse to end position
    MoveMouseHuman(start, end, 300 + rand() % 200);

    fx = end.x * (65535.0f / fScreenWidth);
    fy = end.y * (65535.0f / fScreenHeight);

    ZeroMemory(&input[1], sizeof(INPUT));
    input[1].type = INPUT_MOUSE;
    input[1].mi.dx = (LONG)fx;
    input[1].mi.dy = (LONG)fy;
    input[1].mi.dwFlags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE;

    ZeroMemory(&input[2], sizeof(INPUT));
    input[2].type = INPUT_MOUSE;
    input[2].mi.dwFlags = MOUSEEVENTF_LEFTUP;

    // Set focus to target window
    SetFocus(hwnd);
    SetForegroundWindow(hwnd);
    SetActiveWindow(hwnd);
    
    // Send input
    SendInput(3, input, sizeof(INPUT));
    return (int)true;
}

MOUSEDLL_API void ProcessMessage(const char *message, const void *param)
{
    if (message == NULL) return;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    switch (ul_reason_for_call)
    {
    case DLL_PROCESS_ATTACH:
    case DLL_THREAD_ATTACH:
    case DLL_THREAD_DETACH:
    case DLL_PROCESS_DETACH:
        break;
    }
    return true;
}

const POINT RandomizeClickLocation(const RECT rect) 
{
    POINT p = {0};
    GetClickPoint(rect.left + (rect.right - rect.left) / 2, 
                  rect.top + (rect.bottom - rect.top) / 2, 
                  (rect.right - rect.left) / 2, 
                  (rect.bottom - rect.top) / 2, 
                  &p);
    return p;
}

const void GetClickPoint(const int x, const int y, const int rx, const int ry, POINT *p) 
{
    p->x = x + (int)(RandomNormalScaled(2 * rx, 0, 1) + 0.5) - (rx);
    p->y = y + (int)(RandomNormalScaled(2 * ry, 0, 1) + 0.5) - (ry);
}

const double RandomNormalScaled(const double scale, const double m, const double s) 
{
    double res = -99;
    while (res < -3.5 || res > 3.5) res = RandomNormal(m, s);
    return (res / 3.5 * s + 1) * (scale / 2.0);
}

const double RandomNormal(const double m, const double s) 
{
    double x1 = 0., x2 = 0., w = 0., y1 = 0., y2 = 0.;

    do {
        x1 = 2.0 * ((double)rand() / (double)RAND_MAX) - 1.0;
        x2 = 2.0 * ((double)rand() / (double)RAND_MAX) - 1.0;
        w = x1 * x1 + x2 * x2;
    } while (w >= 1.0);

    w = sqrt((-2.0 * log(w)) / w);
    y1 = x1 * w;
    y2 = x2 * w;

    return(m + y1 * s);
}