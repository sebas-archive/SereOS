#include <stdio.h>
#include <SDL2/SDL.h>
int main(void){
  int n=SDL_GetNumAudioDrivers(), i;
  printf("SDL %d.%d.%d\n", SDL_MAJOR_VERSION, SDL_MINOR_VERSION, SDL_PATCHLEVEL);
  printf("audio drivers (%d):", n);
  for(i=0;i<n;i++) printf(" %s", SDL_GetAudioDriver(i));
  printf("\n");
  return 0;
}
