require 'json'
root=File.expand_path('~/.config/karabiner')
log=File.expand_path('~/Library/Deskflow/deskflow-diagnostics.log')
cli='/Library/Application Support/org.pqrs/Karabiner-Elements/bin/karabiner_cli'
fallback=ARGV.fetch(0)
abort 'Invalid mode' unless %w[local remote].include?(fallback)
File.open(File.join(root,'deskflow-mode.lock'), File::RDWR|File::CREAT,0600) do |lock|
 lock.flock(File::LOCK_EX)
 mode=fallback
 if File.file?(log)
  File.open(log,'rb') do |f|
   f.seek([f.size-65536,0].max)
   events=f.read.scan(/INFO: (entering|leaving) computer\r?$/)
   mode=events.last[0]=='entering' ? 'local' : 'remote' unless events.empty?
  end
 end
 ok=system(cli,'--set-variables',JSON.generate({'deskflow_remote'=>mode=='remote' ? 1 : 0}))
 abort 'Unable to update Karabiner state' unless ok
 File.write(File.join(root,'deskflow-mode'),mode+"\n")
end
