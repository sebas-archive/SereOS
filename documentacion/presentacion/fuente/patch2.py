src = open("build_redesign.py", encoding="utf-8").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, old[:60]
    src = src.replace(old, new)
rep('pic(s, CAP + "/01_arranque/grub_menu.png", 7.2, 1.95, w=5.4)', 'pic(s, CAP + "/01_arranque/grub_menu.png", 7.2, 1.95, w=4.8)')
rep('pic(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.4, 1.9, w=6.2)\ntb(s, 6.4, 5.85, 6.2, 0.3,',
    '_, sy, _, sh = pic(s, CAP + "/03_terminal/cmd_sysinfo_version.png", 6.4, 1.9, w=6.2)\ntb(s, 6.4, sy + sh + 0.12, 6.2, 0.3,')
open("build_redesign.py", "w", encoding="utf-8").write(src)
print("ok")
