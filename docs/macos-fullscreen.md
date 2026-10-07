# macOS fullscreen application switching

## Report and reproduction

Forum report: [Cmd + Tab still not working on macOS](https://forums.te4.org/viewtopic.php?f=70&t=55240&p=249311#p249311).

Reproduced locally on October 7, 2026 with macOS 27.0.1, ToME 1.7.6,
sdl2-compat 2.32.74, and SDL3 3.4.18. The test used an isolated profile
and posted actual Command-Tab keyboard events with macOS Accessibility permission.

One switch away is insufficient to reproduce the problem. After returning to
the game, the next Command-Tab changed the foreground application to Finder,
but the game stayed above Finder at window level 25. The first switch away
had hidden the game successfully.

## Cause in the current build

The engine requests SDL exclusive fullscreen. On macOS this changes the
display mode and raises the window above ordinary application windows.
SDL normally minimizes this window when it loses focus.

After reactivation, the current SDL stack can restore the display mode while
losing the SDL fullscreen flag. Later focus loss then leaves the game covering
the desktop. Waiting for minimization to finish can also leave the game
minimized when Command-Tab activates it again. SDL's application activation
handler relies on its display's fullscreen-window association to restore it;
the association can already have been cleared by leaving fullscreen.

The observations locate the problem in Cocoa/SDL fullscreen restoration.
They do not establish which SDL version caused the original forum report.

## Fix

`scripts/NativeMain.m` handles application activation notifications:

- On application deactivation, leave exclusive fullscreen and minimize the window.
- On application activation, restore the window and re-enter exclusive fullscreen.
- Disable SDL's automatic minimization on window focus loss, since the application
  notifications now manage these transitions.

These actions apply while the engine's requested mode is fullscreen. Windowed
operation continues normally. Exclusive fullscreen, its window level, and the
game's resolution and UI scale are retained.

## Validation

The test checked the foreground PID, visible window order, SDL fullscreen flag,
window size, engine rendering size, UI scale, and the actual CoreGraphics display
mode. Checking only the foreground PID would have missed the original failure.

| Check | Result |
| --- | --- |
| Five successive Command-Tab away/return cycles | Passed for both activation and visible window order |
| Two cycles with longer waits for minimization | Passed |
| Game fullscreen after returning | SDL exclusive fullscreen, window level 25, 3840 × 2160 rendering, 2× UI scale |
| Desktop after switching away | Original 1920 × 1080 logical display, 3840 × 2160 pixels, 2× backing scale |
| Windowed → fullscreen → windowed | Returned to 1600 × 900 window size; fullscreen retained 3840 × 2160 and 2× UI scale |
| App architecture, signing, and relocated runtime libraries | Passed; engine and all 34 bundled libraries are ARM64 |
| First floor, 100 inscriptions, talent targeting, and all three DLC packs | Passed; first floor generated in 859 ms |

Setting `SDL_ALLOW_TOPMOST=0` made the other application's windows visible, but
left the desktop in the game's display mode after subsequent switches. That
experiment was discarded. Re-entering fullscreen solely on SDL window focus
events also failed intermittently; application activation notifications handle
the minimized-window case.

The tests used separate settings and closed their own game processes. The user's
resolution settings and saves were preserved. Multiple monitors and other macOS
versions remain untested.
