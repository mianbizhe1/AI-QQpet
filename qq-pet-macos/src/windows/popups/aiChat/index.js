(() => {
  const app = {
    data: () => ({
      petName: "小企鹅",
      draft: "",
      loading: false,
      messages: [
        {
          id: Date.now(),
          role: "pet",
          text: "我在这里呀，主人~",
          meta: "",
        },
      ],
    }),

    mounted() {
      this.initMove();
      window.electronAPI.aiChat_m_bus((_event, payload) => {
        if (payload.type === "load") {
          this.petName = payload.data?.petName || "小企鹅";
        }

        if (payload.type === "reply") {
          this.loading = false;
          this.messages.push({
            id: Date.now() + Math.random(),
            role: "pet",
            text: payload.data?.message || "嗯嗯~",
            meta: payload.data?.action && payload.data.action !== "none"
              ? `动作：${payload.data.action}`
              : "",
          });
          this.scrollToBottom();
        }
      });
      window.electronAPI.aiChat_h_bus({ event: "mounted" });
    },

    methods: {
      initMove() {
        if (typeof move === "function") {
          new move({ id: "move" }).init();
        }
      },

      sendMessage() {
        const message = this.draft.trim();
        if (!message || this.loading) return;

        this.messages.push({
          id: Date.now() + Math.random(),
          role: "user",
          text: message,
          meta: "",
        });
        this.draft = "";
        this.loading = true;
        this.scrollToBottom();

        window.electronAPI.aiChat_h_bus({
          event: "message",
          message,
        });
      },

      scrollToBottom() {
        setTimeout(() => {
          const body = this.$refs.body;
          if (body) body.scrollTop = body.scrollHeight;
        }, 0);
      },

      closeWindow() {
        window.electronAPI.aiChat_h_bus({ event: "close" });
      },
    },
  };

  Vue.createApp(app).mount("#aiChatApp");
})();
