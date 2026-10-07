/* Cocoa entry point for the native macOS ToME build. */
#import <Cocoa/Cocoa.h>
#include <SDL2/SDL.h>
#include <unistd.h>

extern int tengine_main(int argc, char **argv);
extern SDL_Window *window;
extern char is_fullscreen;

int main(int argc, char **argv)
{
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        /* Restore exclusive fullscreen through app activation, including Cmd-Tab
         * when Cocoa has already minimized the game's only window. */
        SDL_SetHint(SDL_HINT_VIDEO_MINIMIZE_ON_FOCUS_LOSS, "0");
        NSNotificationCenter *notifications = [NSNotificationCenter defaultCenter];
        [notifications addObserverForName:NSApplicationDidResignActiveNotification
                                  object:application queue:nil usingBlock:^(NSNotification *note) {
            if (window && is_fullscreen) {
                SDL_SetWindowFullscreen(window, 0);
                SDL_MinimizeWindow(window);
            }
        }];
        [notifications addObserverForName:NSApplicationDidBecomeActiveNotification
                                  object:application queue:nil usingBlock:^(NSNotification *note) {
            if (window && is_fullscreen) {
                SDL_RestoreWindow(window);
                SDL_SetWindowFullscreen(window, SDL_WINDOW_FULLSCREEN);
            }
        }];
        NSString *resources = [[NSBundle mainBundle] resourcePath];
        if (resources && [[NSBundle mainBundle] bundleIdentifier]) {
            if (chdir([resources fileSystemRepresentation]) != 0) {
                perror("Cannot enter the game resource directory");
                return 1;
            }
        }
        SDL_SetMainReady();
        return tengine_main(argc, argv);
    }
}
