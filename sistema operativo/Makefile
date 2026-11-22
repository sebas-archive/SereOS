# SereOS v1.0 - Makefile
# Prefer the i686-elf cross compiler; fall back to the host gcc in -m32
# freestanding mode (Arch/CachyOS multilib). Both are supported.
#
# El juego "Pac-man SereOS" es un componente independiente (carpeta hermana
# "../Pac-man SereOS"). Aqui NO hay copia de su logica: se compila su libreria
# freestanding build/sereos/libpacman.a y se enlaza al kernel. GAME_DIR se
# puede sobreescribir:  make GAME_DIR="/otra/ruta/Pac-man SereOS"

CROSS    ?= i686-elf-
CC_CROSS := $(CROSS)gcc

ifeq ($(shell command -v $(CC_CROSS) 2>/dev/null),)
  HOSTMODE := 1
  CC       := gcc -m32
  CFLAGS_ARCH := -DSEREOS_HOST_GCC
else
  HOSTMODE := 0
  CC       := $(CC_CROSS)
  CFLAGS_ARCH :=
endif

AS       := nasm
ASFLAGS  := -f elf32
LD       := $(CC)

# --- componente Pac-man SereOS (libreria freestanding enlazada al kernel) ---
GAME_DIR ?= ../Pac-man SereOS
OS_DIR   ?= $(CURDIR)
# GNU make no maneja espacios en dependencias: se escapa el espacio en el
# grafo y se citan las rutas con espacios en las recipes.
empty        :=
space        := $(empty) $(empty)
GAME_DIR_ESC := $(subst $(space),\ ,$(GAME_DIR))
GAME_LIB     := $(GAME_DIR)/build/sereos/libpacman.a
GAME_LIB_ESC := $(GAME_DIR_ESC)/build/sereos/libpacman.a

WARN     := -Wall -Wextra -Wno-unused-parameter -Wno-address-of-packed-member
CFLAGS   := -std=gnu99 -ffreestanding -fno-pie -fno-pic -fno-stack-protector \
            -fno-asynchronous-unwind-tables -fno-omit-frame-pointer \
            -march=i686 -m32 -mno-sse -mno-mmx -mno-sse2 -O2 $(WARN) $(CFLAGS_ARCH) \
            -I. -Iinclude -Iboot -Ikernel -Idrivers -Imemory -Iprocess \
            -Ifilesystem -Igraphics -Igui -Iapps -Iapps/terminal \
            -Iapps/filemanager -Iapps/sysmonitor -Iapps/about \
            -Iaudio -Ishell -Ilibc

LDFLAGS  := -m32 -T linker.ld -ffreestanding -nostdlib -no-pie -Wl,--build-id=none

SRCS_C   := $(shell find . -name '*.c' -not -path './tools/*' -not -path './docs/*' \
              -not -path './apps/game/*' | sort)
SRCS_S   := $(shell find . -name '*.s' -not -path './tools/*' -not -path './docs/*' \
              -not -path './apps/game/*' | sort)
OBJS     := $(patsubst ./%.c,build/%.o,$(SRCS_C)) $(patsubst ./%.s,build/%.o,$(SRCS_S))
DEPS     := $(OBJS:.o=.d)

all: game-lib sereos.iso

build/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MMD -MP -c $< -o $@

build/%.o: %.s
	@mkdir -p $(dir $@)
	$(AS) $(ASFLAGS) $< -o $@

sereos.bin: $(OBJS) $(GAME_LIB_ESC) linker.ld
	$(LD) $(LDFLAGS) -o $@ $(OBJS) "$(GAME_LIB)" -lgcc
	@grub-file --is-x86-multiboot sereos.bin && echo "[OK] kernel multiboot valido"

# La libreria del juego se construye desde su propio componente. Al compilar
# con el Makefile del componente se le pasa OS_DIR para que use los headers
# de este arbol; el componente es freestanding (sin SDL ni headers Linux).
$(GAME_LIB_ESC):
	@$(MAKE) -C "$(GAME_DIR)" sereos OS_DIR="$(OS_DIR)"

# Reconstruir explicitamente el componente tras cambiar su codigo:
game-lib:
	@$(MAKE) -C "$(GAME_DIR)" sereos OS_DIR="$(OS_DIR)"

# Limpiar el build del componente (no afecta al kernel):
game-clean:
	@$(MAKE) -C "$(GAME_DIR)" clean

# Variante sin peticion de framebuffer: conserva la terminal VGA (entrada 2)
sereos-text.bin: sereos.bin tools/patch_multiboot_text.py
	@python3 tools/patch_multiboot_text.py sereos.bin sereos-text.bin
	@grub-file --is-x86-multiboot sereos-text.bin && echo "[OK] kernel multiboot modo texto valido"

sereos.iso: sereos.bin sereos-text.bin grub.cfg
	@rm -rf isodir
	@mkdir -p isodir/boot/grub
	@cp sereos.bin isodir/boot/sereos.bin
	@cp sereos-text.bin isodir/boot/sereos-text.bin
	@cp grub.cfg isodir/boot/grub/grub.cfg
	@grub-mkrescue -o sereos.iso isodir 2>/dev/null
	@echo "[OK] sereos.iso generada"

# Interactive run (uses KVM when available)
QEMU := qemu-system-i386
KVM  := $(shell test -w /dev/kvm && echo "-enable-kvm -cpu host" || echo "")
QFLAGS := -m 256M -vga std -serial file:serial.log -rtc base=localtime
# SB16 con backend de audio del anfitrion (pipewire/pa/sdl). Si el backend
# no esta disponible, `make run-audio` puede fallar: usa `make run` entonces.
AUDIODEV := pipewire,id=snd0
AFLAGS   := -audiodev $(AUDIODEV) -device sb16,audiodev=snd0

run: sereos.iso
	$(QEMU) $(KVM) $(QFLAGS) -cdrom sereos.iso

# Arranque con audio audible (Sound Blaster 16 + backend del sistema)
run-audio: sereos.iso
	$(QEMU) $(KVM) $(QFLAGS) -cdrom sereos.iso $(AFLAGS)

# Arranque headless con captura de audio a WAV (verificacion real de sonido)
run-audio-wav: sereos.iso
	$(QEMU) $(KVM) $(QFLAGS) -display none -cdrom sereos.iso \
		-audiodev wav,id=snd0,path=audio-capture.wav -device sb16,audiodev=snd0

# Headless: graphical desktop without a host window (for CI / screenshots)
run-headless: sereos.iso
	$(QEMU) $(KVM) $(QFLAGS) -display none -cdrom sereos.iso

# Limpia solo los artefactos del OS. La libreria del juego vive en
# "$(GAME_DIR)/build/sereos/" y NO se borra; para eso usa `make game-clean`.
clean:
	rm -rf build sereos.bin sereos-text.bin sereos.iso isodir serial.log audio-capture.wav docs/screenshots/raw

-include $(DEPS)

.PHONY: all run run-audio run-audio-wav run-headless clean game-lib game-clean
