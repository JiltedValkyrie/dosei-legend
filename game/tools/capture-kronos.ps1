param([string]$OutputPath, [int]$Delay=0, [switch]$ShowBehind, [int]$ViewerId=0)
# Capture the emulator itself; never switch focus or capture the desktop.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class KronosCapture {
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 public delegate bool EnumProc(IntPtr h,IntPtr p);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p,IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
 [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h,System.Text.StringBuilder s,int n);
 public static IntPtr Find(uint pid) {
  IntPtr result=IntPtr.Zero;
  EnumWindows((h,p)=> {uint id;GetWindowThreadProcessId(h,out id);var s=new System.Text.StringBuilder(256);GetWindowText(h,s,256);if(id==pid&&s.ToString().StartsWith("Kronos")){result=h;return false;}return true;},IntPtr.Zero);
  return result;
 }
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out RECT r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h,IntPtr dc,uint flags);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h,IntPtr after,int x,int y,int w,int height,uint flags);
}
'@
[KronosCapture]::SetProcessDPIAware() | Out-Null
if (!$OutputPath) { $OutputPath=Join-Path $PSScriptRoot '../build/generated/kronos-window.png' }
if ($Delay) { Start-Sleep -Seconds $Delay }
$viewer=if ($ViewerId) { Get-Process -Id $ViewerId } else { Get-Process kronos | Select-Object -First 1 }
$window=[KronosCapture]::Find($viewer.Id)
if ($ShowBehind) {
    [KronosCapture]::SetWindowPos($window,[IntPtr]1,0,0,0,0,0x53)|Out-Null
    Start-Sleep -Seconds 2
}
$rect=New-Object KronosCapture+RECT
if (![KronosCapture]::GetWindowRect($window,[ref]$rect)) { throw 'No Kronos window' }
$bitmap=New-Object System.Drawing.Bitmap ($rect.Right-$rect.Left),($rect.Bottom-$rect.Top)
$graphics=[System.Drawing.Graphics]::FromImage($bitmap)
try {
    $dc=$graphics.GetHdc()
    try {
        if (![KronosCapture]::PrintWindow($window,$dc,2)) {
            throw 'Background capture unsupported; desktop capture was not attempted.'
        }
    } finally { $graphics.ReleaseHdc($dc) }
    $bitmap.Save([IO.Path]::GetFullPath($OutputPath),[System.Drawing.Imaging.ImageFormat]::Png)
} finally { $graphics.Dispose(); $bitmap.Dispose() }
