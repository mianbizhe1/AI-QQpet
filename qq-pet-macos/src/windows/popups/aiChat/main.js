const main = {
  window: null,
  show: false,
  name: "aiChat",
  width: 360,
  height: 460,

  cleate(opt = {}) {
    const position = opt.position || [100, 100];
    const x = Math.max(0, Math.trunc(position[0] - this.width / 2));
    const y = Math.max(0, Math.trunc(position[1] - this.height - 20));

    windowsMain.open({
      name: this.name,
      loadFile: "popups/aiChat",
      jsFiles: ["./util/move.js"],
      default: {
        width: this.width,
        height: this.height,
        x,
        y,
        alwaysOnTop: true,
        notChangeSize: true,
      },
      created: ({ vm, preloads }) => {
        // 获取 electron 模块（因为 nodeIntegration: true）
        const _require = eval("require");
        const { ipcMain, desktopCapturer, screen } = _require("electron");

        // 注册截图 IPC handler - 在主进程上下文执行 desktopCapturer
        ipcMain.handle("screenshot_capture", async () => {
          try {
            const primaryDisplay = screen.getPrimaryDisplay();
            const { width, height } = primaryDisplay.size;
            const scaleFactor = primaryDisplay.scaleFactor;

            const sources = await desktopCapturer.getSources({
              types: ['screen'],
              thumbnailSize: {
                width: Math.floor(width * scaleFactor),
                height: Math.floor(height * scaleFactor)
              }
            });

            if (!sources || sources.length === 0) {
              return { success: false, error: '无法获取屏幕源' };
            }

            const primarySource = sources[0];
            const thumbnail = primarySource.thumbnail;

            if (!thumbnail || thumbnail.isEmpty()) {
              return { success: false, error: '截图为空' };
            }

            // 返回 PNG 的 data URL
            const dataUrl = thumbnail.toDataURL();
            return { success: true, dataUrl };
          } catch (error) {
            console.error('[screenshot] capture failed:', error);
            return { success: false, error: String(error) };
          }
        });

        preloads({
          aiChat_h_bus_m: async (_event, payload = {}) => {
            if (payload.event === "mounted") {
              vm.webContents.send("aiChat_m_bus_h", {
                type: "load",
                data: {
                  petName: getPetInfoOne("name", "info") || "小企鹅",
                },
              });
              return;
            }

            if (payload.event === "close") {
              this.doClose();
              return;
            }

            if (payload.event === "message") {
              const text = String(payload.message || "").trim();
              if (!text) return;

              try {
                const brain = global.initAIBrain && global.initAIBrain();
                const decision = brain && brain.chatWithAgent
                  ? await brain.chatWithAgent(text)
                  : { dialogue: "我的AI大脑还没醒，等我一下下~" };
                const replyMessage = String(decision && decision.dialogue || "").trim() || "嗯嗯，我听见啦~";

                vm.webContents.send("aiChat_m_bus_h", {
                  type: "reply",
                  data: {
                    message: replyMessage,
                    action: decision.action || "none",
                    reason: decision.reason || "",
                  },
                });
              } catch (error) {
                console.error("[aiChat] message failed:", error);
                vm.webContents.send("aiChat_m_bus_h", {
                  type: "reply",
                  data: {
                    message: "我刚刚卡了一下，再说一次好吗？",
                    action: "none",
                    reason: String(error && error.message || error),
                  },
                });
              }
            }
          },
        });
      },
      onload: () => {
        this.show = true;
      },
      onshow: (win) => {
        this.window = win;
        this.show = true;
      },
      onclose: () => {
        this.window = null;
        this.show = false;
      },
    }).then((win) => {
      this.window = win;
      this.show = true;
    }).catch((error) => {
      console.log(error);
    });
  },

  doClose() {
    if (this.window) {
      this.window.close();
    }
    this.show = false;
  },
};

module.exports = main;
