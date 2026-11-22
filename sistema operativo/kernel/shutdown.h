/* kernel/shutdown.h - apagado real del equipo (ACPI + puertos de emulador)
 *
 * API publica que consume el menu del escritorio. La implementacion vive en
 * kernel/shutdown.c e incluye la preparacion ordenada (silencio de audio,
 * cierre de ventanas con guardado de estado, pantalla de despedida con la
 * tipografia real del sistema y el logo oficial) y una cascada de mecanismos
 * de apagado, de ACPI a los puertos que emulan QEMU, Bochs y VirtualBox,
 * terminando en una parada segura si nada funciona. sereos_restart() usa la
 * misma pantalla con "Reiniciando..." y reinicia por el controlador 8042.
 */
#ifndef SEREOS_SHUTDOWN_H
#define SEREOS_SHUTDOWN_H

/* Apaga el equipo. Prepara el sistema y no retorna cuando el apagado
 * funciona; si ningun mecanismo responde, deja el equipo detenido (cli+hlt)
 * con el aviso "Ya puedes apagar el equipo con seguridad". */
void sereos_shutdown(void);

/* Reinicia el equipo: silencia el audio, muestra la pantalla "Reiniciando..."
 * durante ~1 s y envia el pulso de reset del controlador de teclado
 * (outb(0x64, 0xFE)). Si el reset no responde, deja la CPU detenida. */
void sereos_restart(void);

/* 1 si el apagado se puede intentar en esta maquina. SereOS siempre puede
 * intentarlo: ACPI cuando existe y, si no, la cascada de puertos/aviso. */
int sereos_shutdown_available(void);

#endif /* SEREOS_SHUTDOWN_H */
