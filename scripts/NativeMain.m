/* Cocoa entry point for the native macOS ToME build. */
#import <Cocoa/Cocoa.h>
#include <SDL2/SDL.h>
#include <unistd.h>

extern int tengine_main(int argc, char **argv);

int main(int argc, char **argv)
{
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        NSString *resources = [[NSBundle mainBundle] resourcePath];
        if (resources && [[NSBundle mainBundle] bundleIdentifier]) {
            if (chdir([resources fileSystemRepresentation]) != 0) {
                perror("Cannot enter the game resource directory");
                return 1;
            }
        }
        SDL_SetHint(SDL_HINT_VIDEO_MAC_FULLSCREEN_SPACES, "1");
        SDL_SetHint("SDL_VIDEO_MAC_FULLSCREEN_MENU_VISIBILITY", "1");
        SDL_SetMainReady();
        return tengine_main(argc, argv);
    }
}
