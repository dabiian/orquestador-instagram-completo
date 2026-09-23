class InstagramFollowbackJSMixin:
    def _write_text_with_emojis_js(self, element, text: str) -> bool:
        """
        Inserta texto por JS soportando:
        - textarea
        - input
        - contenteditable div

        Además dispara eventos para que Instagram detecte el cambio.
        """
        try:
            if element is None:
                self.log.warning("No se recibió elemento para escribir por JS.")
                return False

            script = """
            const el = arguments[0];
            const text = arguments[1];

            if (!el) return { ok: false, reason: 'no-element' };

            el.focus();

            const isTextarea = el.tagName === 'TEXTAREA';
            const isInput = el.tagName === 'INPUT';
            const isContentEditable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';

            try {
                if (isTextarea || isInput) {
                    const proto = isTextarea
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;

                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    const setter = descriptor && descriptor.set;

                    if (setter) {
                        setter.call(el, text);
                    } else {
                        el.value = text;
                    }
                } else if (isContentEditable) {
                    el.innerHTML = '';
                    el.textContent = text;
                } else {
                    return { ok: false, reason: 'unsupported-element' };
                }

                el.dispatchEvent(new InputEvent('input', {
                    bubbles: true,
                    cancelable: true,
                    data: text,
                    inputType: 'insertText'
                }));

                el.dispatchEvent(new Event('change', {
                    bubbles: true
                }));

                el.dispatchEvent(new KeyboardEvent('keydown', {
                    bubbles: true,
                    cancelable: true,
                    key: 'Process'
                }));

                el.dispatchEvent(new KeyboardEvent('keyup', {
                    bubbles: true,
                    cancelable: true,
                    key: 'Process'
                }));

                let finalValue = '';

                if (isTextarea || isInput) {
                    finalValue = el.value || '';
                } else if (isContentEditable) {
                    finalValue = el.textContent || '';
                }

                return { ok: true, value: finalValue };
            } catch (e) {
                return { ok: false, reason: String(e) };
            }
            """

            result = self.browser.driver.execute_script(script, element, text)

            if not result or not result.get("ok"):
                self.log.warning("Falló inserción JS: %s", result)
                return False

            final_value = str(result.get("value", "")).strip()
            expected_value = str(text).strip()

            if final_value != expected_value:
                self.log.warning(
                    "Mismatch al escribir por JS. Esperado=%s | Actual=%s",
                    expected_value,
                    final_value,
                )
                return False

            self.log.info("Texto insertado correctamente por JS.")
            return True

        except Exception as e:
            self.log.warning("Error escribiendo texto con JS: %r", e)
            return False

    def _get_reply_input_current_text(self, input_box) -> str:
        try:
            script = """
            const el = arguments[0];
            if (!el) return '';

            const isTextarea = el.tagName === 'TEXTAREA';
            const isInput = el.tagName === 'INPUT';
            const isContentEditable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';

            if (isTextarea || isInput) {
                return el.value || '';
            }

            if (isContentEditable) {
                return el.textContent || '';
            }

            return '';
            """
            value = self.browser.driver.execute_script(script, input_box)
            return str(value or "").strip()
        except Exception:
            return ""

    def _write_reply_text_preserving_mention_js(self, input_box, reply_text: str) -> bool:
        """
        Conserva el @usuario que Instagram prellena al responder
        y agrega el reply generado después.
        """
        try:
            existing_text = self._get_reply_input_current_text(input_box).strip()

            if existing_text:
                final_text = f"{existing_text} {reply_text}".strip()
            else:
                final_text = reply_text.strip()

            return self._write_text_with_emojis_js(input_box, final_text)

        except Exception as e:
            self.log.warning("Error escribiendo reply preservando mención: %r", e)
            return False