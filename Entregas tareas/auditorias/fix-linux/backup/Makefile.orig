# PAC-MAN SereOS - Makefile del componente independiente
#
# Objetivos:
#   make          -> Linux (SDL2): build/pacman-sereos
#   make linux    -> idem
#   make sereos   -> libreria freestanding build/sereos/libpacman.a
#   make test     -> harness de core + smoke Linux (SDL_VIDEODRIVER=dummy)
#   make clean    -> borra build/
#
# No modifica el sistema operativo: kernel-sys enlaza la libreria.

CC       ?= cc
AR       ?= ar
OS_DIR   ?= ../sistema operativo

CFLAGS   ?= -O2 -g
WARN      := -Wall -Wextra -Wno-unused-parameter
INCLUDES  := -Iinclude -Isrc/core -Isrc/render -Iassets -Iassets/fonts
BUILD     := build

# ---------------------------------------------------------------------------
# Linux (SDL2)
# ---------------------------------------------------------------------------
SDL_CFLAGS := $(shell pkg-config --cflags sdl2 2>/dev/null || sdl2-config --cflags 2>/dev/null)
SDL_LIBS   := $(shell pkg-config --libs sdl2 2>/dev/null || sdl2-config --libs 2>/dev/null)

LINUX_SRCS := $(wildcard src/core/*.c) $(wildcard src/render/*.c) \
              $(wildcard src/platform/linux/*.c) \
              $(wildcard assets/*.c) $(wildcard assets/fonts/*.c)
LINUX_OBJS := $(patsubst %.c,$(BUILD)/linux/obj/%.o,$(LINUX_SRCS))
LINUX_BIN  := $(BUILD)/pacman-sereos

# ---------------------------------------------------------------------------
# SereOS (freestanding, sin SDL)
# ---------------------------------------------------------------------------
CFLAGS_SEREOS := -m32 -std=gnu99 -ffreestanding -fno-pie -fno-pic \
                 -fno-stack-protector -fno-asynchronous-unwind-tables \
                 -march=i686 -mno-sse -mno-mmx -O2 $(WARN)
INCLUDES_SEREOS := -Iinclude -Isrc/core -Isrc/render -Iassets \
                   -I"$(OS_DIR)/include" -I"$(OS_DIR)/boot" \
                   -I"$(OS_DIR)/kernel" -I"$(OS_DIR)/drivers" \
                   -I"$(OS_DIR)/memory" -I"$(OS_DIR)/process" \
                   -I"$(OS_DIR)/filesystem" -I"$(OS_DIR)/graphics" \
                   -I"$(OS_DIR)/gui" -I"$(OS_DIR)/apps" \
                   -I"$(OS_DIR)/audio" -I"$(OS_DIR)/shell" -I"$(OS_DIR)/libc"
SEREOS_SRCS := $(wildcard src/core/*.c) $(wildcard src/render/*.c) \
               $(wildcard src/platform/sereos/*.c) \
               $(wildcard assets/*.c)
SEREOS_OBJS := $(patsubst %.c,$(BUILD)/sereos/obj/%.o,$(SEREOS_SRCS))
SEREOS_LIB  := $(BUILD)/sereos/libpacman.a

all: linux

linux: $(LINUX_BIN)
	@echo "[pacman] Linux OK -> $(LINUX_BIN)"

$(LINUX_BIN): $(LINUX_OBJS)
	@if [ -z "$(LINUX_SRCS)" ]; then \
		echo "ERROR: no hay fuentes en src/ ni assets/ (implementacion pendiente de migracion)"; \
		exit 1; \
	fi
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(WARN) -o $@ $(LINUX_OBJS) $(SDL_LIBS) -lm
	@echo "[pacman] enlazado $(notdir $@)"

$(BUILD)/linux/obj/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(WARN) -std=c99 $(INCLUDES) $(SDL_CFLAGS) -MMD -MP -c $< -o $@

sereos: $(SEREOS_LIB)
	@echo "[pacman] SereOS OK -> $(SEREOS_LIB)"
	@echo "[pacman] integrar con: apps/apps.c (app_game) y enlazar antes de -lgcc"

$(SEREOS_LIB): $(SEREOS_OBJS)
	@if [ -z "$(SEREOS_SRCS)" ]; then \
		echo "ERROR: no hay fuentes del componente (migracion pendiente)"; \
		exit 1; \
	fi
	@mkdir -p $(dir $@)
	rm -f $@
	$(AR) rcs $@ $(SEREOS_OBJS)

$(BUILD)/sereos/obj/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS_SEREOS) $(INCLUDES_SEREOS) -MMD -MP -c $< -o $@

# ---------------------------------------------------------------------------
# Pruebas
# ---------------------------------------------------------------------------
test: linux
	@if [ -x tests/run_tests.sh ]; then ./tests/run_tests.sh; \
	else echo "ERROR: falta tests/run_tests.sh"; exit 1; fi

clean:
	rm -rf $(BUILD)

-include $(LINUX_OBJS:.o=.d)
-include $(SEREOS_OBJS:.o=.d)

.PHONY: all linux sereos test clean
