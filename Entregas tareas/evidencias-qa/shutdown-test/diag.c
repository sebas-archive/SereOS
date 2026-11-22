/* diag.c - diagnostico temporal: volcar RSDP/FADT/DSDT y _S5 de QEMU */
#include <stdint.h>

static inline void outb_(uint16_t p, uint8_t v){__asm__ volatile("outb %0,%1"::"a"(v),"Nd"(p));}
static inline uint8_t inb_(uint16_t p){uint8_t v;__asm__ volatile("inb %1,%0":"=a"(v):"Nd"(p));return v;}
static inline void outw_(uint16_t p, uint16_t v){__asm__ volatile("outw %0,%1"::"a"(v),"Nd"(p));}
static void putc_(char c){int g=100000;while(!(inb_(0x3FD)&0x20)&&--g){}outb_(0x3F8,(uint8_t)c);}
static void puts_(const char *s){while(*s)putc_(*s++);}
static void hex_(uint32_t v){for(int i=28;i>=0;i-=4){int d=(v>>i)&0xF;putc_(d<10?'0'+d:'a'+d-10);}}
static void u32_(const char *tag,uint32_t v){puts_(tag);hex_(v);puts_("\n");}
static uint8_t rd8_(uint32_t a){return *(const volatile uint8_t *)(uintptr_t)a;}
static uint16_t rd16_(uint32_t a){return (uint16_t)(rd8_(a)|(rd8_(a+1)<<8));}
static uint32_t rd32_(uint32_t a){return (uint32_t)rd8_(a)|((uint32_t)rd8_(a+1)<<8)|((uint32_t)rd8_(a+2)<<16)|((uint32_t)rd8_(a+3)<<24);}
static int sig_(uint32_t a,const char *s){for(int i=0;i<4;i++)if(rd8_(a+i)!=(uint8_t)s[i])return 0;return 1;}
static uint8_t sum_(uint32_t a,uint32_t n){uint8_t s=0;for(uint32_t i=0;i<n;i++)s=(uint8_t)(s+rd8_(a+i));return s;}

static uint32_t find_rsdp(void){
    uint32_t e=(uint32_t)rd16_(0x40E)<<4;
    uint32_t r[3][2]={{e,1024},{0x9FC00,0x400},{0xE0000,0x20000}};
    for(int k=0;k<3;k++)for(uint32_t a=r[k][0];a+20<=r[k][0]+r[k][1];a+=16){
        if(sig_(a,"RSD ")&&rd8_(a+4)=='P'&&sum_(a,20)==0){
            u32_("RSDP=",a);
            return a;
        }
    }
    return 0;
}
static uint32_t find_fadt(uint32_t rsdp){
    uint32_t t=0,use_x=0;uint8_t rev=rd8_(rsdp+15);
    if(rev>=2){uint32_t x=rd32_(rsdp+24);if(x&&sig_(x,"XSDT")){t=x;use_x=1;}}
    if(!t){t=rd32_(rsdp+16);}
    if(!t){puts_("no table\n");return 0;}
    u32_("table=",t);u32_(" table_len=",rd32_(t+4));u32_(" tsum=",sum_(t,rd32_(t+4)));
    uint32_t len=rd32_(t+4);uint32_t es=use_x?8:4;
    for(uint32_t i=0;i<(len-36)/es;i++){
        uint32_t e=rd32_(t+36+i*es);
        if(sig_(e,"FACP")){u32_("FADT=",e);u32_(" fadt_len=",rd32_(e+4));return e;}
    }
    return 0;
}
static void dump_dsdt(uint32_t dsdt){
    if(!dsdt||dsdt>0x20000000u){puts_("dsdt fuera de rango\n");return;}
    uint32_t len=rd32_(dsdt+4);
    u32_("DSDT=",dsdt);u32_(" DSDT_len=",len);
    if(len>0x100000u){puts_("len absurda\n");return;}
    puts_("sig4=");for(int i=0;i<4;i++)putc_(rd8_(dsdt+i));puts_("\n");
    /* volcado de la zona con _S5_ */
    for(uint32_t i=0;i+4<len;i++){
        if(rd8_(dsdt+i)=='_'&&rd8_(dsdt+i+1)=='S'&&rd8_(dsdt+i+2)=='5'&&rd8_(dsdt+i+3)=='_'){
            u32_("_S5_ en offset 0x",i);
            puts_("ctx: ");for(uint32_t j=(i>4?i-4:0);j<i+16&&j<len;j++){int d=rd8_(dsdt+j);putc_(d<16?'0':0);}
            puts_("\nbytes: ");
            for(uint32_t j=(i>4?i-4:0);j<i+16&&j<len;j++){int d=rd8_(dsdt+j)>>4;putc_(d<10?'0'+d:'a'+d-10);d=rd8_(dsdt+j)&0xF;putc_(d<10?'0'+d:'a'+d-10);putc_(' ');}
            puts_("\n");
        }
    }
}
void diag_entry(void){
    putc_('\n');
    puts_("DIAG_START\n");
    outb_(0x3F9,0x00);outb_(0x3FB,0x80);outb_(0x3F8,0x01);outb_(0x3F9,0x00);outb_(0x3FB,0x03);outb_(0x3FA,0xC7);outb_(0x3FC,0x0B);
    putc_('\n');
    uint32_t rsdp=find_rsdp();
    if(!rsdp){puts_("sin RSDP\n");for(;;)__asm__ volatile("cli;hlt");}
    uint32_t f=find_fadt(rsdp);
    if(!f){puts_("sin FADT\n");for(;;)__asm__ volatile("cli;hlt");}
    uint32_t pm1a=rd32_(f+0x40),pm1b=rd32_(f+0x44),dsdt=rd32_(f+0x28);
    u32_("pm1a=",pm1a);u32_(" pm1b=",pm1b);
    u32_("pm1a_cnt_read=",inb_(pm1a)|(inb_(pm1a+1)<<8));
    u32_("smi_cmd=",rd32_(f+0x30));u32_(" acpi_enable=",rd8_(f+0x34));
    dump_dsdt(dsdt);
    puts_("DIAG_DONE\n");
    for(;;)__asm__ volatile("cli;hlt");
}
