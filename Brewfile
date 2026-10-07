# ToME 1.7.6 native ARM64 build; use /opt/homebrew/bin/brew.
# Install: /opt/homebrew/bin/brew bundle install --file=Brewfile --no-upgrade
# Check: /opt/homebrew/bin/brew bundle check --file=Brewfile

# Build metadata (Apple Command Line Tools supply clang and make).
brew "pkgconf"

# Window, image and font APIs. Homebrew's sdl2 alias is sdl2-compat.
brew "sdl2-compat"
brew "sdl2_image"
brew "sdl2_ttf"

# Direct image/audio dependencies used by the engine.
brew "libpng"
brew "libogg"
brew "libvorbis"

# Keg-only; scripts/build-native.py sets its pkg-config search path.
brew "openal-soft"

# Native ARM64 runtime with yieldable protected calls and JIT compilation.
brew "luajit"

# Homebrew supplies transitive dependencies, including sdl3 and freetype.
# Other bundled engine libraries are built from the game source.
