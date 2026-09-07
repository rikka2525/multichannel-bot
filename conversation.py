"""Channel-independent conversation rules. No Flask or WhatsApp imports."""
from dataclasses import dataclass

MENU = "ご利用内容を選択してください。\n1：お問い合わせ\n2：アンケート\n\n途中でやり直す場合は reset と送信してください。"

@dataclass(frozen=True)
class ConversationResult:
    reply: str
    next_state: str
    rating: int | None = None
    comment: str | None = None
    reset: bool = False

def build_reply(text: str | None, state: str = "menu") -> ConversationResult:
    if text is None or not text.strip():
        return ConversationResult("このデモはテキストメッセージに対応しています。文字を入力して送信してください。", state)
    value = text.strip()
    if value.lower() == "reset":
        return ConversationResult("入力内容をリセットしました。\n\n" + MENU, "menu", reset=True)
    if state == "menu":
        if value == "1":
            return ConversationResult("お問い合わせ内容を入力してください。", "inquiry")
        if value == "2":
            return ConversationResult("アンケートを開始します。\n満足度を1〜5の数字で入力してください。", "survey_rating")
        return ConversationResult("入力を確認できませんでした。1または2を入力してください。\n\n" + MENU, "menu")
    if state == "inquiry":
        return ConversationResult("お問い合わせありがとうございます。内容を受け付けました。\n\n" + MENU, "menu")
    if state == "survey_rating":
        if value not in {"1", "2", "3", "4", "5"}:
            return ConversationResult("1〜5の数字で満足度を入力してください。", "survey_rating")
        return ConversationResult("ありがとうございます。最後に、ご意見やご感想を入力してください。", "survey_comment", rating=int(value))
    if state == "survey_comment":
        return ConversationResult("アンケートへのご協力ありがとうございました。\n\n" + MENU, "menu", comment=value)
    return ConversationResult(MENU, "menu", reset=True)
