class Autokyo < Formula
  include Language::Python::Virtualenv

  desc "macOS local automation tool for page-by-page ebook viewer workflows"
  homepage "https://github.com/plain127/homebrew-autokyo"
  url "https://github.com/plain127/homebrew-autokyo/archive/refs/tags/v0.1.5.tar.gz"
  sha256 "0b2f73a86c72b022d3c94ebfbcd0d00b2ba515ab98b8b89e9e1cc644210a3d2d"

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
