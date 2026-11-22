#include <stdio.h>
#include <SDL2/SDL.h>
int main(void){
  int n,i;
  if(SDL_Init(SDL_INIT_AUDIO)!=0){printf("SDL_Init AUDIO FAIL: %s\n", SDL_GetError());return 1;}
  printf("driver actual: %s\n", SDL_GetCurrentAudioDriver());
  n=SDL_GetNumAudioDevices(0);
  printf("salidas (%d):\n", n);
  for(i=0;i<n;i++) printf("  [%d] %s\n", i, SDL_GetAudioDeviceName(i,0));
  SDL_Quit();
  return 0;
}
