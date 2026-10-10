/* Cocoa entry point for the native macOS ToME build. */
#import <Cocoa/Cocoa.h>
#include <SDL2/SDL.h>
#include <unistd.h>

extern int tengine_main(int argc, char **argv);

const char *te4_native_resource_path(void)
{
    NSBundle *bundle = [NSBundle mainBundle];
    if (![bundle bundleIdentifier]) return NULL;
    NSString *resources = [[bundle objectForInfoDictionaryKey:@"TE4AssetLayout"] isEqualToString:@"split"]
        ? [[bundle bundlePath] stringByDeletingLastPathComponent] : [bundle resourcePath];
    return [resources fileSystemRepresentation];
}

int main(int argc, char **argv)
{
    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyRegular];
        const char *resources = te4_native_resource_path();
        if (resources) {
            if (chdir(resources) != 0) {
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
