# QQ media cleanup on macOS

`scripts/qq_cleanup_macos.zsh` removes old QQ pictures and emoji files when
they use a lot of space. Chat records stay intact.

1. Audit QQ storage. Nothing changes:

   ```zsh
   scripts/qq_cleanup_macos.zsh audit
   ```

2. Preview pictures and emoji older than 90 days:

   ```zsh
   scripts/qq_cleanup_macos.zsh clean --older-than-days 90 --categories Pic,Emoji
   ```

3. Show the preview and get an explicit yes. The user quits QQ, then run the
   same command with `--execute`.

The script accepts only `Pic` and `Emoji`, previews by default and refuses
to run with `--execute` while QQ is running. Never select `nt_db`, account
folders, preferences, voice messages, videos or received files. Tell the
user that removed media may no longer show in old conversations.
