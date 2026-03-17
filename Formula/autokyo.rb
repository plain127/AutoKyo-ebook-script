class Autokyo < Formula
  include Language::Python::Virtualenv

  desc "macOS local automation tool for page-by-page ebook viewer workflows"
  homepage "https://github.com/plain127/homebrew-autokyo"
  url "https://github.com/plain127/homebrew-autokyo/archive/refs/tags/v0.1.6.tar.gz"
  sha256 "46e7dcda3b849e0d9209c81b4a564ebe76a1d131a60c60f1c4772d91ed19ebcf"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  def post_install
    system bin/"autokyo", "init-config"
  end

  def caveats
    <<~EOS
      Default config created at:
        #{Dir.home}/Library/Application Support/AutoKyo/config.toml

      Edit this file before running `autokyo run`.

      For Codex MCP over local HTTP:
        autokyo mcp-install codex
    EOS
  end

  test do
    assert_match "autokyo", shell_output("#{bin}/autokyo --help")
  end
end
